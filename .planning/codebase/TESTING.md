# Testing Patterns

**Analysis Date:** 2026-04-27

## Test Framework

**Runner:** None.

**Assertion Library:** None.

**Run Commands:** None.

There is **no automated test suite** in this repository. There is no `tests/` directory, no `conftest.py`, no `pytest.ini`, no `tox.ini`, no `unittest` modules, no CI workflow under `.github/`, no test files of any kind. A repo-wide search confirms zero matches:

```bash
find . -type f \( -name "*test*.py" -o -name "*spec*" -o -name "conftest.py" \
                 -o -name "pytest.ini" -o -name "tox.ini" \) \
       -not -path '*/.git/*' -not -path '*/__pycache__/*'
# (no output)
```

This is honest — it is a small, prompt-driven Claude Code plugin. The "code" is mostly markdown that Claude reads, plus six Python utility scripts in `scripts/` (~700 LOC total). The risk surface is real but narrow: schema drift, file-path drift, and tracker formatting regressions.

The remainder of this document describes how the plugin **is currently validated** (manual + dry-run patterns observable in the code and prompts) and what an automated testing strategy would look like if added.

---

## Test File Organization

**Location:** Not applicable — no test files exist.

**Naming:** Not applicable.

**Structure:** Not applicable.

---

## Test Structure

Not applicable. No test scaffolding exists.

---

## Mocking

**Framework:** Not applicable.

**What would need mocking if tests were added:**
- `pandas.read_csv` / `pandas.read_excel` — for `scripts/consolidate_targets.py` and `scripts/mine_connections.py`. Pass small in-memory DataFrames instead of fixture files.
- `openpyxl.Workbook` — for `scripts/tracker_utils.py`. Round-trip through a temp `.xlsx` is probably easier than mocking openpyxl's API.
- Filesystem for `scripts/state.py` — point `STATE_DIR` at a `tmp_path` fixture rather than `~/.job-scout`.
- The Claude in Chrome MCP tools used in `skills/scout-run/SKILL.md` — these can only be exercised end-to-end by a human running `/scout-run` against a real browser session. Out of scope for unit tests.

---

## Fixtures and Factories

**None exist.**

If fixtures were introduced, the obvious starting set:
- A minimal `master_targets.csv` with one company per `data_source` value (`linkedin_connections`, `user_csv`, `scout_discovered`).
- A minimal `Connections.csv` matching LinkedIn's actual export shape (3 prefix rows + header — see `scripts/mine_connections.py:29-46` for the detection logic).
- A `new_rows.json` covering one A-tier, one B-tier, one stale (low LinkedIn job ID), and one duplicate to exercise `tracker_utils.append_rows` end-to-end.
- A `config.json` matching `templates/config.json` with realistic weights.

The empty-row factories already in `scripts/schema.py:109-116` (`empty_master_target_row`, `empty_tracker_row`) would be the natural building blocks for fixtures.

---

## Coverage

**Requirements:** None enforced.

**View Coverage:** Not configured.

---

## Test Types

**Unit Tests:** None.

**Integration Tests:** None.

**E2E Tests:** None automated — the only end-to-end validation is a human typing `/scout-setup` then `/scout-run` and reading the output.

---

## How the Plugin IS Currently Validated

In lieu of an automated suite, the codebase relies on five deliberate runtime/manual checks. Each is documented here so future contributors understand what's already protecting the system.

### 1. Runtime data-directory validator (`scripts/validate_data.py`)

This is the closest thing the plugin has to a test. It is invoked at the top of every `/scout-run` (per `skills/scout-run/SKILL.md:30-34`) and at the end of `/scout-setup` (per `skills/scout-setup/SKILL.md:122-124`):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_data.py "<data_dir>"
```

It checks four things:
- `validate_config` — `<data_dir>/config.json` exists and has the required top-level keys (`data_dir`, `preferences`, `search`, `scoring`).
- `validate_master_targets` — every column in `MASTER_TARGETS_COLUMNS` is present; missing ones are added (never deleted).
- `validate_tracker` — `JobScout_Tracker.xlsx` exists; if not, calls `tracker_utils.create_empty_tracker`.
- `validate_daily_dir` — `<data_dir>/daily/` exists.

It returns JSON like:
```json
{
  "data_dir": "/Users/...",
  "ok": true,
  "checks": {
    "config": {"ok": true, "message": "ok"},
    "master_targets": {"ok": true, "message": "added missing columns: ['ats_provider']"},
    ...
  }
}
```

Exit codes: `0` = all green, `1` = unrecoverable. **This is run on every invocation, so any contract-breaking change will surface on the very next user run.** It's a continuous integrity check, not a test, but it catches the same class of bugs.

### 2. State-pointer dry-run (`scripts/state.py resolve`)

Before doing anything else, `/scout-run` calls `python3 scripts/state.py resolve` (see `skills/scout-run/SKILL.md:24-28`). This is effectively a "is the plugin set up?" smoke test:
- Exit 0 → prints resolved `data_dir` to stdout.
- Exit 2 → tells the user to run `/scout-setup` and stops.

This guards against the failure mode the README cites: *"files dropping in different directories"* (`scripts/state.py:11-13`).

### 3. Tracker append idempotency (`scripts/tracker_utils.py append`)

`append_rows` in `scripts/tracker_utils.py:152-232` deduplicates by LinkedIn job ID, flags stale entries, and rewrites the entire file with deterministic formatting. The script is **safe to run repeatedly** with the same input — re-running just produces "skipped_duplicate" counts. This is a soft form of regression testing: the same `new_rows.json` always produces the same `JobScout_Tracker.xlsx`. The summary it prints to stdout (added/skipped/flagged counts) is captured into `<data_dir>/daily/<DATE>/run_log.json` and is human-reviewable after each run.

### 4. Manual smoke test of `/scout-run`

Per `README.md:44-46`:
> Run your first search:  `/scout-run`. This brings up Chrome, runs Pass 1 → Pass 2 → Pass 3 with explicit budgets, scores listings, and produces a daily report + tracker update. Takes 15–30 minutes.

And per `README.md:48-50`:
> After your first manual run confirms everything works, schedule a task that calls `/scout-run` on whatever cadence you want.

The pattern is explicit: **the user manually runs once**, inspects `<data_dir>/daily/<TODAY>/JobScout_Report_<TODAY>.md`, then schedules. The schedule is only trusted after a manual confirmation.

The "Honest notes" section that every report must include (`skills/scout-run/SKILL.md:211-212`, `skills/job-scout/SKILL.md:107-114`) functions as a self-audit — the model is required to flag when results are thin, when the same companies keep recycling, or when LinkedIn is blocking JD reads. A user reviewing this section is performing manual quality validation.

### 5. Version-bump discipline + schema versioning

The `MASTER_TARGETS_VERSION` integer in `scripts/schema.py:36` and the matching migration block in `validate_data.py` form a primitive contract:
- Adding a column requires bumping the version.
- The auto-migration in `validate_master_targets` ensures older user data dirs continue to load on upgrade.

This isn't tested, but it's a **manual review checkpoint** — a reviewer should reject any PR that adds a column to `MASTER_TARGETS_COLUMNS` without bumping `MASTER_TARGETS_VERSION` and verifying the validator handles the migration.

---

## Common Patterns

### Async Testing
Not applicable — there is no async code. All Python is synchronous, single-threaded scripting. The browser interactions (Pass 1/2/3 in `skills/scout-run/SKILL.md`) are orchestrated by Claude through MCP tool calls, not by Python.

### Error Testing
Not formalized. Error paths in `scripts/` rely on:
- `try/except ImportError` for missing dependencies (returns exit 1 with a `pip install` hint).
- `try/except (OSError, json.JSONDecodeError)` for state file corruption (returns empty dict and falls back).
- Tuple returns `(False, "<message>")` from validators that surface to the JSON output.

A future test suite would want fixture cases for each: missing `pandas`, malformed `config.json`, missing `master_targets.csv`, corrupted `state.json`.

---

## Recommended Testing Strategy (If Added)

If automated tests are introduced, the smallest valuable suite would be **pytest-based unit tests covering only the deterministic helpers**. The browser-driven skill prompts and MCP integrations should remain manually validated — testing them would require mocking the entire Claude in Chrome surface, which is not worth the effort for a personal-tooling plugin.

### Tier 1 — must-have (~1 day of work)

`tests/test_schema.py`:
- `empty_master_target_row()` returns a dict with exactly `MASTER_TARGETS_COLUMNS` as keys, all empty strings.
- `empty_tracker_row()` returns a dict with exactly `TRACKER_JSON_KEYS` as keys, all empty strings.
- `len(TRACKER_COLUMNS) == len(TRACKER_JSON_KEYS) == len(TRACKER_COL_WIDTHS)` (the three lists must stay aligned — this is asserted nowhere in the code today).

`tests/test_tracker_utils.py`:
- `extract_job_id` parses 10+ digit numbers from LinkedIn URLs and returns `None` for non-URLs.
- `is_stale_by_id` flags IDs below `STALE_LINKEDIN_JOB_ID_THRESHOLD` (`4_200_000_000`).
- `get_row_fill` returns `STALE_FILL` for status containing "Stale", `A_TIER_FILL` for tier "A", and `NO_FILL` for unknown tier.
- Round-trip: `append_rows` followed by `get_dedup_set` returns the same job IDs.
- Idempotency: calling `append_rows` twice with the same input produces the same row count the second time (all duplicates).

`tests/test_state.py`:
- Patch `STATE_DIR` to `tmp_path`. Verify `read_state` returns `{}` when missing, returns dict when present, returns `{}` when malformed.
- `write_state` creates `STATE_DIR` and writes JSON with `data_dir`, `plugin_version`, `last_setup_iso`.
- `resolve_data_dir` prefers state file, then walks `LEGACY_DATA_DIRS`, then returns empty string.

### Tier 2 — nice-to-have (~1 day)

`tests/test_validate_data.py`:
- Each of the four validators (`validate_config`, `validate_master_targets`, `validate_tracker`, `validate_daily_dir`) tested against a `tmp_path` data directory.
- **Migration test** — write an old-schema `master_targets.csv` (missing `ats_provider`, `ats_board_url`), run `validate_master_targets`, confirm columns added, confirm existing user-added columns preserved at the end.

`tests/test_consolidate_targets.py`:
- `normalize_company_name` strips punctuation, lowercases, drops common suffixes (`inc`, `llc`, `ltd`).
- `detect_company_column` finds the company column under various aliases (`Company`, `Organization`, `Employer`, `Name`).
- `merge_duplicates` collapses two rows for the same company, takes max of `linkedin_connection_count`, unions `connection_names`.

`tests/test_mine_connections.py`:
- `detect_header_rows` handles the standard 3-prefix-row LinkedIn export and a no-prefix variant.
- Encoding fallback (`utf-8` → `latin-1` → `cp1252`) is exercised with a fixture in each encoding.

### Tier 3 — JSON template validation

`tests/test_templates.py`:
- `templates/config.json` parses as JSON.
- `templates/candidate_profile.json` parses as JSON.
- `.claude-plugin/plugin.json` parses as JSON and has `name`, `version`, `description`.
- The `version` strings in `plugin.json` and the highest-versioned `SKILL.md` are equal (catches the common forget-to-bump-the-manifest mistake).

### Things deliberately NOT worth testing

- The `skills/**/SKILL.md` prompts themselves. They are read by Claude, not executed by Python.
- The Chrome MCP interactions in `skills/scout-run/SKILL.md` Steps 1–4. Mocking the MCP surface is more work than it's worth and the manual smoke run already exercises this end-to-end.
- The actual scoring decisions (Step 5 of `scout-run`). These are model judgment calls, not deterministic code.
- Output report formatting in `<data_dir>/daily/<DATE>/JobScout_Report_<DATE>.md`. Generated by Claude, not by a template engine.

### Suggested CI

If a suite is added, the lightest possible CI:
```yaml
# .github/workflows/test.yml
name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.10' }
      - run: pip install pandas openpyxl pytest
      - run: pytest tests/ -v
```

No coverage gate, no linter — match the project's current "minimal ceremony" stance.

---

*Testing analysis: 2026-04-27*

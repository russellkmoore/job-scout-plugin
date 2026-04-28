# Phase 1: Schema migration + paths + foundational cleanup — Research

**Researched:** 2026-04-27
**Domain:** Pandas/openpyxl schema migration + pytest fixture testing + macOS file-permission hardening + PEP 668-compliant install hints + path SSOT cleanup
**Confidence:** HIGH (every claim grounded in directly-read source at `scripts/*.py` or live registry probes; one critical CONCERNS-audit correction surfaced)

## Summary

Phase 1 is **mechanical and surgical**, not architectural. Six SCH requirements bump `master_targets.csv` to v=4 (additive cols `ats_slug_confidence` + `last_ats_hit_date`) plus tracker `source` + `ats_provider` cols, ensure `runs.jsonl` and `daily/<DATE>/ats_raw/` paths exist, and lock the migration behind a single pytest fixture test. Seven CON requirements clean up tech debt in the same files being touched. None of the work crosses architectural boundaries — `schema.py`, `validate_data.py`, `tracker_utils.py`, `state.py`, `consolidate_targets.py`, `mine_connections.py`, `templates/config.json`, `references/file-contract.md`, and three skill docs are the entire footprint. No new dependencies (pytest is the test framework; `httpx` and `rapidfuzz` arrive in Phase 2).

**One CONCERNS-audit correction surfaced:** CON-01 (`consolidate_targets.py:270` KeyError) is **already guarded** in the actual current source. Line 270 reads `len(master[master['already_applied'].str.upper() == 'Y']) if 'already_applied' in master.columns else 0` — the `if 'already_applied' in master.columns else 0` short-circuit prevents the KeyError. CONCERNS.md describes the historical pre-guard form. The dead summary block (lines 269–272) should still be deleted because it can never produce a non-zero result on a v=3+ file, and `already_applied` was schema-trimmed in v3 — but the framing is "delete dead code," not "fix a crash."

**Primary recommendation:** Sequence the work in this dependency order — (1) `schema.py` constants bump first, (2) `validate_data.py` migration logic to honor the bump, (3) `tracker_utils.py` HEADER extension with read-back compatibility for v3 xlsx files, (4) `tests/test_migration.py` fixture round-trip, (5) `state.py` permissions + `LEGACY_DATA_DIRS` deletion, (6) cleanup items in `consolidate_targets.py` + `mine_connections.py` + every script's `ImportError` handler, (7) `file-contract.md` + skill-doc edits last. The schema test in step 4 must pass before any tracker-touching code merges.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CSV column schema (master_targets) | `scripts/schema.py` (constants) | `scripts/validate_data.py` (migration) | SSOT convention — only place column names live |
| Tracker xlsx schema | `scripts/schema.py` (HEADERS/JSON_KEYS/COL_WIDTHS triple) | `scripts/tracker_utils.py` (the only writer) | Tracker xlsx is single-writer by design |
| File-path registry | `skills/job-scout/references/file-contract.md` | `scripts/validate_data.py` (mkdir for dirs) | "No alternate paths. No fallbacks. No 'or'." |
| State pointer + perms | `scripts/state.py` | — | Already centralized; just needs chmod calls added |
| Migration test infrastructure | `tests/test_migration.py` (new) | `tests/fixtures/master_targets_v3.csv` (new) | Carved-out exception to no-test-suite rule |
| Status-value validation | `scripts/schema.py` (`STATUS_VALUES` const) | `scripts/tracker_utils.py:append_rows` (validates on write) | Validation runs at the write boundary, not on read |
| Install-hint string | Per-script `ImportError` handler | — | Convention — five existing handlers all updated identically |
| Default value SSOT | `templates/config.json` | Skill prompts reference template, never inline | Stop drifting `companies_per_day` 5-vs-8 |

## User Constraints

> No CONTEXT.md exists for this phase. The constraints below are derived from `PROJECT.md` "Key Decisions," `REQUIREMENTS.md` SCH/CON sections, `ROADMAP.md` Phase 1 success criteria, and `CLAUDE.md` "Locked decisions."

### Locked Decisions (do NOT re-research alternatives)

- **`MASTER_TARGETS_VERSION = 4`** — additive only; new cols `ats_slug_confidence` (float 0.0–1.0 or empty) + `last_ats_hit_date` (ISO date or empty) appended at the end. v0.3 readers must not crash on v=4 CSV (pandas tolerates extra columns naturally; this is verified by the round-trip assertion in `tests/test_migration.py`).
- **Tracker columns** — `source` + `ats_provider` extend `TRACKER_COLUMNS` / `TRACKER_JSON_KEYS` / `TRACKER_COL_WIDTHS` in `schema.py`. All tracker writes still go through `tracker_utils.py:_write_tracker` only.
- **Test framework** — pytest. Fixture lives at `tests/fixtures/master_targets_v3.csv`. Test file at `tests/test_migration.py`. This is the ONLY test in v0.4 — not a precedent for a broader suite.
- **No new dependencies in Phase 1.** `httpx` + `rapidfuzz` arrive in Phase 2; pytest is dev-only and runs out-of-process via the `pytest` CLI.
- **`os.path.expanduser()` at the boundary** in every CLI — already convention; do not replace with `pathlib.Path.expanduser()` mid-cleanup.
- **Plain `print()` for logging** — no `logging` module. `ERROR:` prefix to stderr; machine-consumable JSON as last `print()` of any CLI.
- **`try / except ImportError` install hint pattern** — every third-party dep surfaces an actionable command. Phase 1 changes the recommended command (`--break-system-packages` → `pipx`/venv) but keeps the pattern.
- **`tracker_utils.py:HEADERS`** is SSOT for tracker columns. **`scripts/schema.py:MASTER_TARGETS_COLUMNS`** is SSOT for CSV columns. **`skills/job-scout/references/file-contract.md`** is SSOT for paths. Never inline elsewhere.

### Claude's Discretion (research and recommend)

- Migration shape: version-aware (`if file_version < 4: run_migration_3_to_4()`) vs the existing column-by-column additive pattern. (See **Domain Knowledge → Schema migration mechanics** below for recommendation.)
- `STATUS_VALUES` enum membership and behavior on unknowns (reject / warn-coerce / warn-passthrough).
- `pipx` vs `python3 -m venv` install-hint copy.
- `LEGACY_DATA_DIRS` strategy — delete + setup-prompt vs. deprecate-with-warning.
- `companies_per_day` default canonical strategy — pick a number, defer-to-template, or symbolic constant.
- `state.json` chmod timing — once at write or every read.
- `runs.jsonl` rotation/size policy (Phase 1 only needs the file path; recommendation informs Phase 2 writer).
- `mine_connections.py` header-detection failure mode (warn-and-continue vs error-and-abort).
- `ats_raw/` directory granularity in `file-contract.md`.

### Deferred Ideas (OUT OF SCOPE for Phase 1)

- Any code that **calls** ATS APIs (Phase 2+).
- Async/concurrent dispatcher (Phase 2).
- Detection logic, two-factor gate (Phase 3).
- New providers, JSON-LD fallback, filtering (Phase 4).
- Cross-source dedup, scoring rubric edits, enrichment (Phase 5).
- Run-summary block, marketing-page deletion, version normalization (Phase 6).
- Replacing pandas/openpyxl with sqlite/stdlib-csv (deferred to v0.5+).
- Generic test suite beyond `tests/test_migration.py`.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCH-01 | `validate_data.py` ensures `runs.jsonl` exists at start of `/scout-run` | Add a 5-line `validate_runs_log()` validator following existing `(ok, message)` tuple pattern; touches the file with `open(path, 'a').close()` if absent |
| SCH-02 | `validate_data.py` ensures `daily/<DATE>/ats_raw/` exists before Pass 1 | Modify existing `validate_daily_dir()` OR add `ensure_today_subdirs(data_dir, today)` called by `/scout-run` Step 0; recommend the latter — `validate_data.py` runs at startup, before `<DATE>` is known |
| SCH-03 | `MASTER_TARGETS_VERSION` → 4; add `ats_slug_confidence` + `last_ats_hit_date` cols | One-line const bump + two list entries in `MASTER_TARGETS_COLUMNS`; auto-handled by existing `validate_master_targets()` add-missing-columns logic |
| SCH-04 | Tracker `source` + `ats_provider` cols via `tracker_utils.HEADERS` (= `schema.TRACKER_COLUMNS`) | Extend `TRACKER_COLUMNS` (14→16), `TRACKER_JSON_KEYS` (14→16), `TRACKER_COL_WIDTHS` (14→16). `_write_tracker` rebuilds workbook on every append — old 14-col xlsx files survive because `iter_rows` returns whatever exists and `len < HEADERS` is already padded with `None` at line 134-135 |
| SCH-05 | `tests/test_migration.py` round-trips v3 fixture | New `tests/` dir, new fixture CSV with realistic rows + a user-added column to verify preservation, new pytest test file. Three assertions match the success criteria verbatim |
| SCH-06 | `file-contract.md` lists `runs.jsonl` and `daily/<DATE>/ats_raw/` | Two new rows in the existing tables; one in "Persistent files in `{data_dir}`," one in "Per-run output (always under `daily/`)" |
| CON-01 | Drop dead `already_applied` summary block in `consolidate_targets.py:269-272` | **Already guarded — does not crash today.** Reframe as "delete dead code that can never trigger on v=3+ schema" |
| CON-02 | `STATUS_VALUES` enum + tracker-append validation | Add frozenset to `schema.py`; validate in `tracker_utils.append_rows` before `existing_rows.append(row_list)` at line 218 |
| CON-03 | `mine_connections.py` header-detection warning + post-skip column validation | Add `print("WARNING: ...", file=sys.stderr)` in `detect_header_rows` fallback path; validate `df.columns` after `pd.read_csv` and abort if no recognizable name/company column |
| CON-04 | Switch all `ImportError` hints from `--break-system-packages` to `pipx`/venv | 5 sites: `validate_data.py:29`, `tracker_utils.py:31`, `consolidate_targets.py:26`, `mine_connections.py:25`, plus the new test file's import error message |
| CON-05 | Resolve `LEGACY_DATA_DIRS` contradiction with file-contract.md | Recommendation: **delete the legacy chain** + add a one-time migration check in `state.py:resolve_data_dir` that exits 2 with a clear message naming any detected legacy dir |
| CON-06 | Single canonical `companies_per_day` default across 3 sites | Recommendation: **pick `5` to match `templates/config.json`** + **remove the inline numeric quote** from `scout-run/SKILL.md:73` and `search-config.md:43`; replace with "from `config.search.companies_per_day` (default in `templates/config.json`)" |
| CON-07 | `state.json` perm hardening — `os.chmod(STATE_PATH, 0o600)` + `os.chmod(STATE_DIR, 0o700)` | Add chmod calls in `write_state` after `os.makedirs` and after `json.dump`; also add idempotent re-chmod in `read_state` to harden existing-user state.json files on first v0.4 run |

## Standard Stack

### Core (verified against pip index 2026-04-28)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pandas` | 2.2.3 (current installed) / 3.0.2 latest | DataFrame I/O for CSV migration test | [VERIFIED: pip index versions pandas → 3.0.2 latest; `python3 -c "import pandas; print(pandas.__version__)"` → 2.2.3 on dev machine]. Already a project dep; no change. |
| `openpyxl` | 3.1.5 latest | Tracker xlsx read-back / write in test fixture | [VERIFIED: pip index versions openpyxl → 3.1.5]. Already a project dep; no change. |
| `pytest` | 8.x stable (9.0.3 latest, 8.4.x is the most recent stable major) | Migration test runner | [VERIFIED: pip index versions pytest → 9.0.3 latest, 8.4.2 stable]. Recommend `pytest>=8,<10` (allows pytest 8 and 9). pytest 8 is what most CI environments default to today; pytest 9 is fresh. Either works — both support `tmp_path` fixtures, parametrize, and the `pytest tests/test_migration.py` invocation pattern from the success criteria. |

### Supporting

None. Phase 1 introduces no new runtime dependencies. The new test file imports only `pytest`, `pandas`, plus the project's own `scripts/schema.py` and `scripts/validate_data.py` via the existing sibling-bootstrap pattern.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest (stdlib) | unittest needs zero install; pytest needs one. But the test file is 30 lines either way, pytest's `tmp_path` fixture and clean assert syntax are cleaner, and the success criterion explicitly says `python3 -m pytest tests/test_migration.py`. Stick with pytest. |
| Version-aware migration (`if v < 4: ...`) | Column-by-column additive (current pattern) | Recommendation: **stay with column-by-column additive** for Phase 1 — see Architecture Patterns → Pattern 1 below. |
| `pipx` install hint | `python3 -m venv` install hint | Both work; `pipx` is one-line and idiomatic for CLI tools. Recommendation: surface BOTH on one line — see Code Examples → Install hint copy below. |
| Delete `LEGACY_DATA_DIRS` | Keep with deprecation warning | Recommendation: **delete entirely**. The list grew at v0.3.2 (per CONCERNS.md), the contract in `file-contract.md` says "no fallbacks," and the maintenance cost of "is this user on legacy?" is real. See Architecture Patterns → Pattern 4 below. |

**Installation (test framework only):**
```bash
# Recommended (idempotent — pipx skips if already installed)
pipx install pytest

# OR (project-local venv)
python3 -m venv .venv && source .venv/bin/activate && pip install pytest pandas openpyxl
```

**Version verification:**
```bash
pip index versions pytest    # 8.4.2 (stable) | 9.0.3 (latest)
pip index versions pandas    # 2.2.3 (most-installed) | 3.0.2 (latest)
pip index versions openpyxl  # 3.1.5 (latest)
```

[VERIFIED: pip index versions probes 2026-04-28 from this dev machine.]

## Architecture Patterns

### System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                       Phase 1 data flow                              │
└──────────────────────────────────────────────────────────────────────┘

  /scout-run startup           /scout-setup               pytest run
       │                            │                          │
       ▼                            ▼                          ▼
┌──────────────┐            ┌──────────────┐           ┌─────────────────┐
│ state.py     │            │ state.py     │           │ test_migration  │
│ resolve()    │            │ write_state  │           │ .py             │
│              │            │  + chmod 0o600│          │                 │
│ → data_dir   │            │  + chmod 0o700│          │ loads fixture   │
└──────┬───────┘            └──────────────┘           │ master_targets  │
       │                                               │ _v3.csv         │
       ▼                                               └────────┬────────┘
┌──────────────────────────────────────┐                        │
│ validate_data.py <data_dir>          │                        │
│   validate_config()                  │                        ▼
│   validate_master_targets()  ────────┼────────┐    ┌─────────────────┐
│     reads schema.MASTER_TARGETS_     │        │    │ validate_data   │
│     COLUMNS (now v=4 with 2 new      │        │    │ .validate_      │
│     cols at the end)                 │        │    │ master_targets  │
│   validate_tracker()                 │        │    │ runs against    │
│     ensures HEADERS = 16 cols        │        │    │ fixture in      │
│   validate_daily_dir()               │        │    │ tmp_path        │
│   validate_runs_log()        [NEW]   │        │    └────────┬────────┘
└──────┬───────────────────────────────┘        │             │
       │                                        │             ▼
       ▼                                        │    ┌─────────────────┐
┌──────────────────────────────────────┐        │    │ assert:         │
│ /scout-run continues — Step 0        │        │    │  - all v3 rows  │
│ ensures daily/<DATE>/ats_raw/        │        │    │    preserved    │
│ via mkdir -p (or                     │        │    │  - new cols     │
│  validate_data.ensure_today_subdirs) │        │    │    present+empty│
└──────────────────────────────────────┘        │    │  - user-added   │
                                                │    │    col survives │
       ┌────────────────────────────────────────┘    │  - v3-shape     │
       ▼                                             │    reader can   │
┌──────────────────────────────────────┐             │    parse v=4    │
│ tracker_utils.append_rows            │             │    CSV          │
│   reads schema.TRACKER_JSON_KEYS     │             └─────────────────┘
│   (now 16 keys: …source, ats_provider│
│   appended)                          │
│   validates row.application_status   │
│   ∈ schema.STATUS_VALUES             │
│   _write_tracker rebuilds 16-col     │
│   xlsx (old 14-col xlsx grows on     │
│   first append — verified by         │
│   iter_rows + None-padding)          │
└──────────────────────────────────────┘
```

### Recommended Project Structure

```
scripts/
├── schema.py                    # Bump VERSION, extend column lists, add STATUS_VALUES
├── state.py                     # Delete LEGACY_DATA_DIRS, add chmod calls
├── validate_data.py             # Add validate_runs_log; switch install hint
├── tracker_utils.py             # Extend HEADERS, add status validation, switch install hint
├── consolidate_targets.py       # Drop dead already_applied summary, switch install hint
└── mine_connections.py          # Add WARNING + post-skip column validation, switch install hint

tests/                           # NEW dir
├── __init__.py                  # Empty (pytest finds tests without it, but standard)
├── test_migration.py            # NEW — pytest test
└── fixtures/
    └── master_targets_v3.csv    # NEW — checked-in v=3 fixture

skills/
├── job-scout/references/
│   ├── file-contract.md         # Add runs.jsonl + daily/<DATE>/ats_raw/ entries
│   └── search-config.md         # Defer companies_per_day default to template
└── scout-run/SKILL.md           # Defer companies_per_day default to template

templates/config.json            # No change — companies_per_day stays at 5
```

### Pattern 1: Migration mechanics — stay with column-by-column additive (HIGH confidence)

**What:** The current `validate_master_targets()` at `scripts/validate_data.py:63-93` iterates `MASTER_TARGETS_COLUMNS` and adds any missing column with empty-string default. It is **version-blind by design** — no `if v < N` branches, no migration registry, no schema version stamped in the CSV itself.

**Why keep it that way for Phase 1:**

1. **Three pytest assertions in SCH-05 are exactly what column-by-column additive gives you.** "Rows preserved" → trivially true; we never delete or filter. "New cols present + empty" → exactly what the `for col in MASTER_TARGETS_COLUMNS: if col not in existing_cols: df[col] = ""` loop produces. "v0.3 code reads v=4 CSV without crash" → pandas auto-handles extra columns; old code reads the columns it knows about and ignores the rest.
2. **Version-aware migration is only worth its cost when migrations DROP, RENAME, or TRANSFORM data.** v0.4 has none of those. Phase 1 adds two columns; Phase 2+ may add more, but every locked decision is "additive only."
3. **`MASTER_TARGETS_VERSION` is read by `state.py` and surfaced to the user in `state.json:plugin_version`** — its purpose is *user-visible breadcrumbing*, not migration dispatch. Bumping it to 4 is the breadcrumb. The migration is unchanged.
4. **Adding migration dispatch requires storing the file's current version somewhere** — either in a header comment row (breaks pandas), in a sentinel column (defeats "additive"), or in a sidecar file (breaks SSOT). All three have higher costs than the bug they prevent. Defer until v0.5+ when a non-additive change actually exists.

**When to use:** Every Phase 1 schema change (SCH-03, SCH-04). When a future phase needs a transform/rename, that's the trigger to introduce version-aware migration — not earlier.

**Example:**
```python
# scripts/schema.py — change is exactly this:
MASTER_TARGETS_COLUMNS = [
    "company_name",
    "industry",
    "career_page_url",
    "ats_provider",
    "ats_board_url",
    "connection_names",
    "linkedin_connection_count",
    "application_status",
    "fit_notes",
    "last_checked",
    "data_source",
    "ats_slug_confidence",   # NEW v=4 — float 0.0–1.0 or empty string
    "last_ats_hit_date",     # NEW v=4 — ISO date or empty string
]

MASTER_TARGETS_VERSION = 4  # v4: added ats_slug_confidence + last_ats_hit_date for v0.4 ATS sourcing.
```

**No change to `validate_master_targets()`.** The existing logic at lines 80-91 already handles new-column addition correctly:

```python
# scripts/validate_data.py — UNCHANGED
for col in MASTER_TARGETS_COLUMNS:
    if col not in existing_cols:
        df[col] = ""
        added.append(col)

if added:
    extras = [c for c in df.columns if c not in MASTER_TARGETS_COLUMNS]
    df = df[MASTER_TARGETS_COLUMNS + extras]   # canonical first, user-added at end
    df.to_csv(path, index=False)
    return True, f"added missing columns: {added}"
```

**Source:** `scripts/validate_data.py:63-93` (read 2026-04-27).

### Pattern 2: Tracker-column extension — `_write_tracker` already handles short rows (HIGH confidence)

**What:** `tracker_utils._write_tracker` at line 264-315 rebuilds the entire xlsx workbook on every append. `load_tracker` at line 132-136 already pads short rows to `len(HEADERS)`:

```python
for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
    row_list = list(row)
    if len(row_list) < len(HEADERS):
        row_list.extend([None] * (len(HEADERS) - len(row_list)))
    rows.append(row_list)
```

**Why this matters:** A v=3 14-column xlsx file passed through `load_tracker → append_rows → _write_tracker` will (a) read the 14 columns correctly, (b) get padded to 16 with `None`, (c) be re-emitted as a 16-column xlsx with the new `source` and `ats_provider` columns empty for existing rows. **No migration code needed in `tracker_utils.py`.** The success criterion "existing rows are populated as empty (back-compatible — older Excel filters still work)" is satisfied for free.

**Caveat (CON-20, deferred to Phase 5):** `_write_tracker` line 293 `if col > len(HEADERS): break` actively drops user-added columns beyond `HEADERS`. Phase 1 inherits this bug (any user who manually added an `ats_provider` column to their xlsx before v0.4 ships would have it overwritten — but the chance of this exact collision is near-zero given the column names). CON-20's full fix lands in Phase 5; Phase 1 just extends `HEADERS` from 14 to 16 and accepts the existing limitation.

**Example:**
```python
# scripts/schema.py — extend three lists in lockstep
TRACKER_COLUMNS = [
    "Date Found", "Job Title", "Company", "Location", "Comp Range",
    "Score", "Tier", "Connections", "Match Notes", "Job URL",
    "Resume Tailored", "Resume File", "Status", "Notes",
    "Source",          # NEW v0.4 — ats:greenhouse|ats:lever|...|linkedin
    "ATS Provider",    # NEW v0.4 — ats:greenhouse|...|empty
]

TRACKER_JSON_KEYS = [
    "date_found", "job_title", "company", "location", "comp_range",
    "score", "tier", "connections", "match_notes", "job_url",
    "resume_tailored", "resume_file", "status", "notes",
    "source",          # NEW
    "ats_provider",    # NEW
]

TRACKER_COL_WIDTHS = [12, 45, 20, 25, 20, 8, 6, 12, 40, 50, 14, 30, 16, 50,
                      18, 16]  # source, ats_provider — narrow display
```

```python
# scripts/tracker_utils.py:append_rows row_list construction (existing line 201-216)
# extends naturally — just append two .get() calls:
row_list = [
    row_dict.get("date_found", datetime.now().strftime("%Y-%m-%d")),
    # ... existing 13 entries ...
    row_dict.get("notes", ""),
    row_dict.get("source", ""),         # NEW
    row_dict.get("ats_provider", ""),   # NEW
]
```

**Source:** `scripts/tracker_utils.py:120-143, 201-216, 264-315` (read 2026-04-27).

### Pattern 3: pytest test shape — fixture-driven round-trip with tmp_path (HIGH confidence)

**What:** The carved-out test exception is `tests/test_migration.py`. Recommended shape: one pytest module with **three test functions**, each addressing one of the three SCH-05 assertions.

**Why three functions, not one:** Pytest reports failures per test. If one assertion regresses, the user sees exactly which contract broke (rows preserved? new cols empty? v0.3 reader compatible?). A single monolithic `test_migration()` blurs the signal.

**Fixture format:** Realistic — at least 3 rows, including (a) one with all canonical v=3 columns populated, (b) one with a user-added `my_notes` column at the end, (c) one with empty/sparse fields. Don't use a 1-row stub — won't catch column-reorder bugs that only appear when extras exist.

**The "v0.3 code path can still read v=4 CSV" assertion:** Don't check out the v0.3 git tag — too brittle. Instead, **synthesize a v=3-shape reader inline:**

```python
# Inline synthesis: simulate v=3 by reading only the first 11 columns explicitly
v3_columns = [
    "company_name", "industry", "career_page_url", "ats_provider", "ats_board_url",
    "connection_names", "linkedin_connection_count", "application_status",
    "fit_notes", "last_checked", "data_source",
]
df_v3_view = pd.read_csv(migrated_csv, usecols=lambda c: c in v3_columns)
assert list(df_v3_view.columns) == v3_columns  # same shape v0.3 expected
assert len(df_v3_view) == 3  # all rows still readable
```

This proves "extra columns are tolerated" without depending on git history.

**Test skeleton (drop-in for Phase 1 plan):**
```python
# tests/test_migration.py
"""
Migration round-trip test for the v3→v4 master_targets.csv schema bump.

Carved-out exception to the v0.4 "no test suite" rule. The fixture
tests/fixtures/master_targets_v3.csv represents a v=3-era user file with:
  - 3 realistic rows (mix of populated and sparse)
  - 11 canonical v=3 columns
  - 1 user-added column ("my_notes") at the end

After migration via validate_data.validate_master_targets(), we assert:
  1. All v3 rows are preserved (zero data loss)
  2. New v=4 columns (ats_slug_confidence, last_ats_hit_date) are present and empty
  3. The user-added column survived at the end
  4. A v=3-shape reader (only-canonical-cols) can still parse the v=4 CSV
"""
import os
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

# Bootstrap project scripts on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from schema import MASTER_TARGETS_COLUMNS, MASTER_TARGETS_VERSION
from validate_data import validate_master_targets

FIXTURE = Path(__file__).parent / "fixtures" / "master_targets_v3.csv"


@pytest.fixture
def migrated_data_dir(tmp_path):
    """Copy the v3 fixture into a tmp data_dir, run the migration, return the path."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    shutil.copy(FIXTURE, data_dir / "master_targets.csv")
    ok, msg = validate_master_targets(str(data_dir))
    assert ok, f"validate_master_targets failed: {msg}"
    return data_dir


def test_schema_version_is_v4():
    """Sanity: the schema constant is at v=4."""
    assert MASTER_TARGETS_VERSION == 4


def test_all_v3_rows_preserved(migrated_data_dir):
    """SCH-05 assertion (a): all v3 rows preserved."""
    df = pd.read_csv(migrated_data_dir / "master_targets.csv")
    fixture_df = pd.read_csv(FIXTURE)
    assert len(df) == len(fixture_df), "row count changed during migration"
    # Each fixture company_name appears exactly once in the migrated file
    for name in fixture_df["company_name"]:
        assert (df["company_name"] == name).sum() == 1, f"company {name!r} lost or duplicated"


def test_new_v4_columns_present_and_empty(migrated_data_dir):
    """SCH-05 assertion (b): new columns present and empty."""
    df = pd.read_csv(migrated_data_dir / "master_targets.csv")
    assert "ats_slug_confidence" in df.columns
    assert "last_ats_hit_date" in df.columns
    # Empty for every row (string "" or NaN both acceptable; pandas reads "" as NaN)
    assert df["ats_slug_confidence"].fillna("").eq("").all()
    assert df["last_ats_hit_date"].fillna("").eq("").all()


def test_user_added_column_survives(migrated_data_dir):
    """User-added columns must survive at the end (never delete user data)."""
    df = pd.read_csv(migrated_data_dir / "master_targets.csv")
    assert "my_notes" in df.columns, "user-added column was dropped"
    # Should be the last column (canonical first, extras at end — see validate_data.py:88)
    assert df.columns[-1] == "my_notes"


def test_v3_reader_can_parse_v4_csv(migrated_data_dir):
    """SCH-05 assertion (c): v0.3 code path can still read the v=4 CSV without crash.

    Simulate v0.3 by reading only the v=3 canonical columns explicitly.
    pandas tolerates extra columns naturally; this proves the contract.
    """
    v3_columns = [
        "company_name", "industry", "career_page_url", "ats_provider", "ats_board_url",
        "connection_names", "linkedin_connection_count", "application_status",
        "fit_notes", "last_checked", "data_source",
    ]
    df_v3_view = pd.read_csv(migrated_data_dir / "master_targets.csv",
                              usecols=lambda c: c in v3_columns)
    assert sorted(df_v3_view.columns) == sorted(v3_columns)
    fixture_df = pd.read_csv(FIXTURE)
    assert len(df_v3_view) == len(fixture_df)
```

**Why this shape works:**
- Each test is self-describing and maps 1:1 to a SCH-05 assertion line.
- The `migrated_data_dir` pytest fixture isolates each test in `tmp_path` (no test pollution).
- Failures point at exactly one broken contract.
- 60 lines total — small enough to review by eye, large enough to catch the four most likely regressions.

**Fixture content (`tests/fixtures/master_targets_v3.csv`) — recommended:**
```csv
company_name,industry,career_page_url,ats_provider,ats_board_url,connection_names,linkedin_connection_count,application_status,fit_notes,last_checked,data_source,my_notes
Stripe,Fintech,https://stripe.com/jobs,greenhouse,https://boards.greenhouse.io/stripe,Alice Smith (Eng Manager); Bob Jones (Director),5,,Strong commerce fit,2026-04-20,linkedin_connections,"investigate Q3"
lululemon,Retail,https://careers.lululemon.com,workday,https://lululemon.wd5.myworkdayjobs.com/careers,,3,Applied 2026-03-12 / no response,Tech leadership ladder is real,2026-04-15,user_csv,
Acme,,,,,,0,Dead,passed on 2026-Q1,2026-01-10,scout_discovered,
```

(11 v=3 cols + 1 user-added `my_notes` col. Three rows: populated, sparse, edge-case.)

**Source:** Pattern derived from existing `scripts/validate_data.py:63-93` semantics and `pytest` 8.x docs.

### Pattern 4: `LEGACY_DATA_DIRS` — delete + setup-prompt (MEDIUM confidence; recommend lock)

**Recommendation:** **Delete `LEGACY_DATA_DIRS` entirely** from `scripts/state.py:32-36` and `resolve_data_dir()` (lines 78-81). When `state.json` is missing, `resolve_data_dir()` returns empty → `state.py resolve` exits 2 → `/scout-run` Step 0 tells the user to run `/scout-setup`. `/scout-setup` adds a one-time check: if any of the three legacy dirs (`~/Documents/JobSearch/scout`, `~/Documents/JobSearch`, `~/Documents/JobScout`) exists and contains `config.json`, prompt:

> Found a Job Scout data directory at `~/Documents/JobSearch/`. Use this as your data_dir? [Y/n]

If yes, write the path into `state.json` and proceed. If no, prompt for a fresh path.

**Why delete vs keep-with-warning:**

| Approach | Pro | Con |
|----------|-----|-----|
| **Delete + setup-prompt** | One-time pain (only users without state.json), enforces SSOT, file-contract.md is honest | Existing users on legacy paths must re-run `/scout-setup` once |
| Keep with deprecation warning | Zero user disruption | Contradicts file-contract.md "no fallbacks"; the list will keep growing every time someone moves directory conventions; ambiguity persists indefinitely |
| Delete without prompt | Cleanest code | Existing users see "no Job Scout state found" and don't know their old data is fine, just unpointed |

The setup-prompt path is **strictly better than option 3** — same code-cleanliness benefit, no surprise for existing users. It is **strictly better than option 2** — bounded migration cost vs. unbounded legacy maintenance.

**Pitfall to call out:** If an existing user has data at a non-listed location (e.g., `~/JobSearch/`), the setup-prompt won't auto-detect it. They'll go through normal setup and point `state.json` at their existing path manually. This is correct behavior — file-contract.md says "no fallbacks," and asking the user once is more transparent than secretly walking a list.

[ASSUMED] User base size for this transition is small enough that a one-time prompt won't generate support load. Ungrounded — this is a personal-use plugin per `PROJECT.md`, but worth a check with the user during plan-discussion.

### Pattern 5: STATUS_VALUES enum — frozenset + warn-and-coerce on append (MEDIUM confidence)

**Canonical members:** `{"Active", "Applied", "Interviewing", "Offer", "Rejected", "Dead", "Closed"}` plus the empty string `""` for "not yet processed."

**Behavior on unknown:** **warn-and-coerce** — log `WARNING: unknown application_status '<value>' in row <i>; coercing to 'Active'` to stderr; replace the row's `application_status` with `Active` before appending. **Do not reject the append.**

**Rationale:**

- **Reject (option a) is too strict.** A typo in a programmatic feed (e.g., `application_status="dad"` from a poorly-merged consolidate) would crash the entire `/scout-run` write and leave the report half-built. Violates the existing convention "never delete user data."
- **Warn-and-passthrough (option c) defeats the purpose.** If we accept `"DEAD"` (uppercase), `"dead."` (trailing dot), and `"Dead "` (trailing space), the magic-string drift is unfixed.
- **Warn-and-coerce (option b) honors both invariants** — write succeeds (no data loss in the rest of the row), and the `Status` column thereafter contains canonical-only values that downstream `application_status == "Dead"` filters can trust.

**Where it runs:** In `tracker_utils.append_rows`, before `existing_rows.append(row_list)` at line 218. This catches both fresh `/scout-run` writes AND `tracker rebuild` invocations that re-process old rows.

**Source of truth:** Define `STATUS_VALUES` in `scripts/schema.py` immediately below `MASTER_TARGETS_VERSION`:

```python
# scripts/schema.py
STATUS_VALUES = frozenset({
    "",                # not yet processed
    "Active",          # currently considering
    "Applied",         # applied, awaiting response
    "Interviewing",    # interview in progress
    "Offer",           # offer extended
    "Rejected",        # explicit rejection
    "Dead",            # company is no longer hiring / role gone
    "Closed",          # we closed the loop ourselves (declined to apply or withdrew)
})
```

**Validator helper (also in `schema.py`):**
```python
def normalize_application_status(value):
    """
    Validate or coerce an application_status value.
    Returns (canonical_value, was_coerced: bool).
    Unknown values coerce to "Active" with was_coerced=True.
    """
    if value is None:
        return "", False
    s = str(value).strip()
    # Case-insensitive match against canonical set
    for canonical in STATUS_VALUES:
        if s.lower() == canonical.lower():
            return canonical, s != canonical  # was_coerced if case differed
    return "Active", True  # unknown — coerce + flag
```

**Caller (`tracker_utils.append_rows`):**
```python
from schema import normalize_application_status
# ... inside the for row_dict in new_rows loop, before row_list construction:
raw_status = row_dict.get("status", "")
canonical, coerced = normalize_application_status(raw_status)
if coerced:
    print(f"WARNING: row {added}: unknown status {raw_status!r} → coerced to {canonical!r}",
          file=sys.stderr)
row_dict["status"] = canonical
```

**Where validation runs (chosen by inspection of locked decisions):** in `tracker_utils.append_rows` (write boundary), NOT in `validate_data.validate_master_targets` (read boundary). Reasoning: status values live in the tracker xlsx, not in `master_targets.csv`. The `master_targets.csv` `application_status` column is free-form per user notes and shouldn't be coerced (that would surprise users who type `"Applied 2026-03-12 / no response"` per the existing convention at `scripts/schema.py:30`). Two different columns, two different validation needs.

[ASSUMED] The 7 canonical members above are sufficient. The user may want different member names (e.g., `"Hold"`, `"Ghosted"`). Flag for plan-discussion.

### Anti-Patterns to Avoid

- **Version-aware migration dispatch in Phase 1.** Adds complexity (need to stamp version into the file or sidecar) for a problem that doesn't exist yet (no destructive migrations in v0.4).
- **Refactoring `_write_tracker` to do incremental appends.** This is CON-20 / Phase 5 territory. Phase 1 keeps the existing rebuild-everything pattern and just extends `HEADERS`.
- **Unifying the `LEGACY_DATA_DIRS` deletion with the v=3→v=4 schema migration.** Two different concerns, two different reverts if either breaks. Keep them in separate plans.
- **Hand-rolling a "schema version checker" that reads the CSV header to dispatch.** pandas already tolerates extra columns; the check is unnecessary.
- **Putting `STATUS_VALUES` validation in `validate_data.validate_master_targets`.** That's the read path for `master_targets.csv`, not the tracker write path. Wrong column, wrong file.
- **Recommending `pip install --break-system-packages`** anywhere in the new install hint. The whole point of CON-04 is removing this. Even as "fallback."
- **Quoting the `companies_per_day` default as a number** in any skill doc. The whole point of CON-06 is single-source. Replace with "default in `templates/config.json`" — let the user inspect the file if they want the number.
- **`os.chmod(STATE_PATH, 0o600)` only at write time.** Existing users have 0644 state.json files from v0.3. Add idempotent re-chmod to `read_state` so the first v0.4 read hardens them automatically.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema migration dispatch table | Custom `MIGRATIONS = [...]` registry mapping versions to functions | Existing column-by-column additive in `validate_master_targets` | Only useful when migrations transform data; v0.4 doesn't |
| Test framework | argparse-driven manual test runner | pytest 8.x | Already standard; success criteria mandates `pytest` |
| File version detection | Read first line of CSV, sniff column count, infer version | Just bump `MASTER_TARGETS_VERSION` in schema.py | Version stamp is for user-facing breadcrumbing, not dispatch |
| Tracker incremental update | "Append only the new rows to the existing xlsx" | Existing `_write_tracker` rebuild | CON-20 territory; Phase 5; out of scope |
| Status enum library | `enum.Enum` subclass with `_missing_` hook | `frozenset` of strings | enum.Enum has comparison gotchas with raw strings; frozenset is what `STALE_LINKEDIN_JOB_ID_THRESHOLD = 4_200_000_000` precedent uses (module-level constant of literal value) |
| chmod-on-read race-condition handling | `try/except PermissionError` ladder | `os.chmod(path, 0o600)` is idempotent | macOS chmod on a file you own never fails. Multi-user shared-machine concern is theoretical for this single-user plugin |
| File-contract path templating | DSL or YAML schema for paths | Plain markdown table | file-contract.md is human-read; markdown is fine |

**Key insight:** Phase 1 is **mostly subtraction and renaming**, not new logic. Most of these "don't hand-roll" items are warnings against over-engineering — the existing patterns are already the right answer.

## Runtime State Inventory

This is a schema migration phase. Re-cast as: "what state on a real user's machine is affected by Phase 1 changes?"

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| **Stored data** | (1) `~/Documents/JobSearch/master_targets.csv` (v=3 file with 11 cols + possible user extras) — Phase 1 adds 2 cols at the end. (2) `~/Documents/JobSearch/JobScout_Tracker.xlsx` (v=3-shape with 14 cols) — Phase 1 extends to 16. (3) `~/.job-scout/state.json` (existing 0644 perm). | (1) auto-migrated by `validate_data.validate_master_targets` on next `/scout-run`. (2) auto-migrated on next `tracker_utils.append_rows`. (3) re-chmod'd by `state.read_state` on first v0.4 invocation. **All three are zero-touch for the user.** |
| **Live service config** | None — no external services configured by Phase 1. | None. |
| **OS-registered state** | None — Phase 1 doesn't register tasks, services, or daemons. The user may have a launchd/cron entry calling `/scout-run` but that survives unchanged. | None. |
| **Secrets/env vars** | `${CLAUDE_PLUGIN_ROOT}` env var set by Claude Code runtime; unaffected. No secrets in scope. | None. |
| **Build artifacts** | `scripts/__pycache__/*.pyc` — stale `.pyc` files reference old `MASTER_TARGETS_VERSION = 3`. | Python auto-invalidates on source change (mtime check); no manual action needed. |

**Items found in legacy `LEGACY_DATA_DIRS` chain (CON-05 specific):** any user with data at `~/Documents/JobSearch/scout/`, `~/Documents/JobSearch/`, or `~/Documents/JobScout/` whose `state.json` is missing currently relies on the fallback chain at `state.py:78-81`. After deletion, those users see "No Job Scout state found" on their next `/scout-run` and must run `/scout-setup` once. The setup-prompt approach in Pattern 4 above auto-detects their existing dir and writes it into `state.json` — so this is one extra `/scout-setup` invocation, not a re-creation of their data.

**Nothing found in category:** Live service config, OS-registered state, secrets/env — verified by grep across `scripts/` and `skills/`.

## Common Pitfalls

### Pitfall 1: Tracker xlsx round-trip silently drops user-added columns

**What goes wrong:** A user manually added a `Recruiter` column to their tracker xlsx (column 15, beyond the v=3 14-col `HEADERS`). After Phase 1 ships and the next `/scout-run` calls `tracker_utils.append_rows`, `_write_tracker` rebuilds the workbook with `if col > len(HEADERS): break` (line 293) — but `len(HEADERS)` is now 16, so columns 15 and 16 are now filled by `Source` and `ATS Provider`. The user's data in column 15 is **silently overwritten**.

**Why it happens:** CON-20 is about exactly this defect, deferred to Phase 5. Phase 1 doesn't fix it but creates the conditions for it to bite (extending `HEADERS` from 14 to 16 changes which existing user columns are at risk).

**How to avoid in Phase 1:**
- Document the risk in the Phase 1 commit message and the `tracker_utils.py` change.
- Recommend in the migration test: include a 4th assertion that warns if a real user xlsx is detected with > 14 columns (if test is extended later).
- **Do NOT try to fix CON-20 in Phase 1.** That's a 50-line refactor of `_write_tracker` to capture extras into a passthrough buffer; out of scope.
- For users with custom tracker columns: tell them in the v0.4 release notes to back up their xlsx before first v0.4 `/scout-run` and to manually re-add their custom columns to position 17+ after the run.

**Warning signs:** A user reports "my Recruiter column is empty" after upgrading.

### Pitfall 2: pytest discovers nothing because of module-import error

**What goes wrong:** `tests/test_migration.py` imports `validate_data` via the sibling-bootstrap pattern. If pandas isn't installed in the test environment (e.g., the user runs `python3 -m pytest` from a venv that doesn't have pandas), pytest reports `ModuleNotFoundError: pandas` at collection time — *not* in any individual test — and exits with a confusing "no tests collected" message.

**Why it happens:** `validate_data.py:26-30` raises `SystemExit` on `ImportError` (the project's existing convention). Pytest treats `SystemExit` during collection as a hard fail.

**How to avoid:**
- Pytest invocation in CI/local must be from an environment with pandas + openpyxl available.
- The pytest `conftest.py` (optional) can `pytest.skip("pandas not available")` if the import fails, but the simpler fix is **document the test prereqs** in `tests/test_migration.py` module docstring: *"Run from a Python environment with pandas + openpyxl + pytest installed. See `pipx install pytest` or `python3 -m venv .venv && pip install pytest pandas openpyxl`."*

**Warning signs:** "0 collected" output, no test failures, but no green either.

### Pitfall 3: `mine_connections.py` warning-but-continue masks a fatal mismatch

**What goes wrong:** The fix for CON-03 is to add a `WARNING:` when `detect_header_rows` falls through to the `(3, 'latin-1')` default. But if the post-fallback `pd.read_csv(skiprows=3)` happens to produce a DataFrame that *looks* parseable (e.g., the file's row 4 is a coincidence of comma-separated text), the warning fires but `mine_connections` continues happily and produces garbage output.

**Why it happens:** Warn-and-continue is only safe if the post-fallback validation actually catches the bad case.

**How to avoid:**
- The CON-03 fix MUST do BOTH: (a) print the warning AND (b) validate that the resolved column set after `pd.read_csv` includes a recognizable name/company column (existing logic at lines 68-76 already finds the company column; extend to also require `first_name`-style match), AND abort with a clear `ERROR:` message if not.
- The recommendation is **error-and-abort on no-recognizable-columns**. If headers can't be resolved, the script's output is meaningless — better to surface a loud failure than to write a garbage `connections_summary.csv` and corrupt the next `consolidate_targets.py` run.

**Warning signs:** `connections_summary.csv` has rows where `company_name` is a person's name (the actual company column was misidentified).

### Pitfall 4: `state.json` chmod fails on shared-NFS or sandboxed home dirs

**What goes wrong:** `os.chmod(STATE_PATH, 0o600)` on a network-mounted home directory or in a sandboxed environment (some corporate macOS configurations) raises `PermissionError`.

**Why it happens:** chmod requires write permission on the file. On owned files in a writable home dir, this is always OK on macOS/Linux. On NFS-mounted homes with root_squash or sandboxed managed-Mac configs, it can fail.

**How to avoid:**
- Wrap the chmod call in a `try/except OSError` that emits a `WARNING: could not chmod state.json — file permissions are <current>; consider hardening manually` to stderr, then **continues** (does not abort).
- Hardening should be best-effort, not a blocker. The plugin still works at 0644; only the multi-user-machine threat model is reduced.

**Warning signs:** Setup completes but a `WARNING: chmod failed` line in stderr that the user might not notice.

### Pitfall 5: Schema bump test passes locally but fails in CI because of pandas version

**What goes wrong:** pandas 2.2.3 (current dev) treats empty CSV cells one way; pandas 3.0.x (latest) may differ subtly (e.g., `NaN` vs `""` for empty strings). The `test_new_v4_columns_present_and_empty` assertion `df["ats_slug_confidence"].fillna("").eq("").all()` is defensive against this, but a test using `df["ats_slug_confidence"].eq("").all()` directly would break across versions.

**Why it happens:** pandas 3.0 introduced changes to NA handling.

**How to avoid:** Use `.fillna("").eq("").all()` (defensive) in any "is the column empty?" assertion, as shown in the test skeleton above. This works on pandas 2.x and 3.x.

**Warning signs:** Local test passes; another machine's identical test fails on the empty-column assertion.

### Pitfall 6: `pipx`-installed pytest can't find project-relative pandas

**What goes wrong:** The user follows the new install hint `pipx install pytest`. pipx installs pytest in its own isolated venv. When `pytest tests/test_migration.py` runs, it uses pipx's pytest venv — which doesn't have pandas. Test fails on import.

**Why it happens:** `pipx` is for **standalone CLI tools**. For project tests, `python3 -m venv` is the right pattern.

**How to avoid:** The Phase 1 install-hint copy must distinguish:

- **For `mine_connections.py` etc. CLI scripts (the existing `ImportError` handlers in `scripts/`):** recommend `pipx`. pandas + openpyxl are runtime deps of the CLI; `pipx install <script-as-app>` doesn't quite fit since these scripts aren't packaged. Recommend `python3 -m venv` for the runtime deps.
- **For `tests/test_migration.py`:** recommend `python3 -m venv .venv && source .venv/bin/activate && pip install pytest pandas openpyxl`. Don't use `pipx install pytest` — pytest needs to run with the project's pandas, not pipx's.

The new copy must clarify both paths. See Code Examples → Install hint copy below.

**Warning signs:** Test fails on `import pandas` even though the user followed the install hint.

## Code Examples

### Install-hint copy (CON-04, multi-script)

**Before (current — 4 sites):**
```python
print("ERROR: pandas not installed. Run: pip install pandas --break-system-packages", file=sys.stderr)
```

**After (recommended; copy verbatim into all 5 sites):**
```python
print(
    "ERROR: pandas not installed. Install with one of:\n"
    "  python3 -m venv ~/.venvs/job-scout && ~/.venvs/job-scout/bin/pip install pandas openpyxl\n"
    "  (then run: source ~/.venvs/job-scout/bin/activate)\n"
    "OR (system-wide via Homebrew on macOS):\n"
    "  brew install python && python3 -m pip install --user pandas openpyxl",
    file=sys.stderr,
)
```

**Rationale:**
- Two paths: user-managed venv (recommended), or `--user` install (works on PEP 668 Homebrew Python on macOS).
- Avoids `pipx` for runtime deps (pipx is for standalone CLIs; pandas is a runtime dep of multiple scripts that share a Python env).
- Avoids `--break-system-packages` entirely.
- Explicit `~/.venvs/job-scout` path so the user has a memorable, project-specific location.

For the test file specifically, recommend `pip install pytest` inside the same venv — keep the README/docs concise. The test file's own docstring should mention prerequisites.

[VERIFIED: Homebrew Python 3.13 on macOS allows `pip install --user` without `--break-system-packages` because `~/Library/Python/3.13/lib/python/site-packages` is not "externally managed." Confirmed via search results — see Sources.]

### `STATUS_VALUES` validator (CON-02, schema.py + tracker_utils.py)

```python
# scripts/schema.py — add below MASTER_TARGETS_VERSION
STATUS_VALUES = frozenset({
    "",                # not yet processed
    "Active", "Applied", "Interviewing", "Offer",
    "Rejected", "Dead", "Closed",
})


def normalize_application_status(value):
    """
    Validate or coerce an application_status value.

    Returns (canonical_value, was_coerced).
    Unknown values coerce to "Active" with was_coerced=True.
    Case-insensitive match against STATUS_VALUES; case-different inputs
    are coerced (and was_coerced=True so the caller can warn).
    """
    if value is None:
        return "", False
    s = str(value).strip()
    for canonical in STATUS_VALUES:
        if s.lower() == canonical.lower():
            return canonical, s != canonical
    return "Active", True
```

```python
# scripts/tracker_utils.py — inside append_rows, before row_list construction (line 200ish)
from schema import normalize_application_status  # add to existing imports

# ... inside the for row_dict in new_rows loop:
raw_status = row_dict.get("status", "")
canonical, coerced = normalize_application_status(raw_status)
if coerced and raw_status:  # don't warn for empty string coercion
    print(
        f"WARNING: row {added}: application_status {raw_status!r} not in STATUS_VALUES; coerced to {canonical!r}",
        file=sys.stderr,
    )
row_dict["status"] = canonical
```

### `state.py` permission hardening (CON-07)

```python
# scripts/state.py — modify write_state and read_state
def write_state(data_dir, plugin_version=None):
    """Write the state pointer. Creates ~/.job-scout/ if needed.
    Hardens perms to 0o700/0o600 best-effort."""
    os.makedirs(STATE_DIR, exist_ok=True)
    _harden_perms(STATE_DIR, 0o700)  # dir
    data_dir = os.path.expanduser(data_dir)
    state = {
        "data_dir": data_dir,
        "plugin_version": plugin_version or "",
        "last_setup_iso": datetime.utcnow().isoformat() + "Z",
    }
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
    _harden_perms(STATE_PATH, 0o600)  # file
    return state


def read_state():
    """Return state dict, or empty dict if not present / unreadable.
    Idempotently re-hardens perms on existing v0.3 state.json files."""
    if not os.path.exists(STATE_PATH):
        return {}
    _harden_perms(STATE_PATH, 0o600)  # idempotent — fixes 0644 from v0.3
    _harden_perms(STATE_DIR, 0o700)
    try:
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _harden_perms(path, mode):
    """Best-effort chmod; warn on failure but don't abort.
    Sandboxed/NFS environments may reject; the plugin still works at default perms."""
    try:
        os.chmod(path, mode)
    except OSError as e:
        print(
            f"WARNING: could not chmod {path} to {oct(mode)}: {e}. "
            f"State file remains at default permissions; consider hardening manually.",
            file=sys.stderr,
        )
```

### `LEGACY_DATA_DIRS` deletion (CON-05)

```python
# scripts/state.py — DELETE lines 28-36 entirely. Replace with:
# (Legacy fallback chain removed in v0.4 — file-contract.md mandates "no fallbacks."
# /scout-setup detects existing legacy dirs and prompts the user once on first v0.4 run.)


def resolve_data_dir():
    """
    Return the user's data directory:
      1. ~/.job-scout/state.json -> data_dir
      2. Empty string if not configured (caller must prompt /scout-setup)
    """
    state = read_state()
    candidate = state.get("data_dir")
    if candidate:
        candidate = os.path.expanduser(candidate)
        if os.path.isdir(candidate):
            return candidate
    return ""
```

```markdown
# skills/scout-setup/SKILL.md — add a new step before existing Step 1:
## Step 0: Detect existing data directory

If `state.json` is missing, check the three legacy locations from v0.3:
  - `~/Documents/JobSearch/scout`
  - `~/Documents/JobSearch`
  - `~/Documents/JobScout`

For each that contains a `config.json`, present:
> Found a Job Scout data directory at `<path>`. Use this as your data_dir? [Y/n]

If the user accepts, write the path into state.json via `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state.py write <path>` and proceed to existing Step 1 (skipping the data_dir prompt). If they decline or no legacy dir is found, fall through to the existing prompt flow.

This step runs once per machine. After state.json exists, /scout-setup never re-checks.
```

### `runs.jsonl` validator addition to `validate_data.py` (SCH-01)

```python
# scripts/validate_data.py — add new validator
def validate_runs_log(data_dir):
    """Ensure runs.jsonl exists; create empty if missing. Idempotent."""
    path = os.path.join(data_dir, "runs.jsonl")
    if not os.path.isfile(path):
        # Touch — empty file is valid JSONL
        open(path, "a").close()
        return True, "created empty runs.jsonl"
    return True, "ok"


# Add to main()'s validator list:
for name, fn in [
    ("config", validate_config),
    ("master_targets", validate_master_targets),
    ("tracker", validate_tracker),
    ("daily_dir", validate_daily_dir),
    ("runs_log", validate_runs_log),  # NEW
]:
```

### `daily/<DATE>/ats_raw/` directory creation (SCH-02)

**Recommendation:** create on-demand from `/scout-run` Step 0 (after `<TODAY>` is known), not from `validate_data.py`. The validator runs at startup before the date is computed.

```bash
# In scout-run/SKILL.md Step 0 (Compute today's run paths section, after computing <TODAY>):
mkdir -p "<data_dir>/daily/<TODAY>/ats_raw"
```

Or, if a Python helper is preferred (cleaner; matches the script convention):

```python
# scripts/validate_data.py — add a new helper for /scout-run to call after date resolution
def ensure_today_subdirs(data_dir, date_str):
    """Create daily/<DATE>/ and daily/<DATE>/ats_raw/ if missing. Idempotent."""
    today_dir = os.path.join(data_dir, "daily", date_str)
    os.makedirs(os.path.join(today_dir, "ats_raw"), exist_ok=True)
    return today_dir


# Expose via CLI subcommand:
# python3 validate_data.py ensure-today <data_dir> <YYYY-MM-DD>
```

The script-helper version is more consistent with the existing convention; the bash version is one line. Recommend the script version — `/scout-run` already calls `validate_data.py` once at Step 0, adding one more invocation is cheap.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pip install --break-system-packages` to install Python deps | `pipx install <cli>` for standalone CLIs / `python3 -m venv` for runtime deps / `pip install --user` for system-wide | PEP 668 (2023, enforced by Debian 12 / Ubuntu 23.04 / Homebrew Python 3.12+) | All 4 existing `ImportError` hints in `scripts/` recommend a deprecated/risky pattern. CON-04 fixes this. |
| `requests.Session` for HTTP across threads | `httpx` sync client (officially thread-safe) | (Phase 2 concern, not Phase 1) — but documented in PROJECT.md locked decisions | N/A for Phase 1 |
| Single-threshold fuzzy dedupe | Tiered confidence band (≥95% auto / 70–95% review / <70% keep both) | (Phase 5 concern) — not Phase 1 | N/A for Phase 1 |
| `fuzzywuzzy` | `rapidfuzz` (MIT, faster) | ~2020 — fuzzywuzzy archived, rapidfuzz is the maintained replacement | (Phase 5 concern) |
| 0644 default umask for state files | `0o600` for files containing path-pointers / 0o700 for parent dirs | Best-practice since UNIX permissions; CON-07 brings this project up to spec | Multi-user shared-Mac systems can no longer read other users' data_dir paths |

**Deprecated/outdated:**
- `pip install --break-system-packages` as the recommended install copy (CON-04 — in scope).
- `LEGACY_DATA_DIRS` fallback chain (CON-05 — in scope).
- Inline numeric defaults for config values quoted in skill prose (CON-06 — in scope).
- Magic-string `application_status` matching (CON-02 — in scope).
- `consolidate_targets.py:269-272` dead summary block referencing a v3-trimmed column (CON-01 — in scope; reframed as "delete dead code, not fix-a-crash").

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The user's installed `python3` (likely Homebrew on macOS) supports `pip install --user` without `--break-system-packages` because `~/Library/Python/3.X/lib/...` is not "externally managed" | Code Examples → Install-hint copy | Hint copy fails on some Linux distros; user falls back to venv (still works, no harm) |
| A2 | The 7 `STATUS_VALUES` members (`Active`, `Applied`, `Interviewing`, `Offer`, `Rejected`, `Dead`, `Closed`) cover all the user's actual statuses | Pattern 5 | If user has additional canonical statuses (e.g., `Hold`, `Ghosted`), enum coerces them to `Active` → silent reclassification |
| A3 | "Warn-and-coerce" is the right strategy for unknown application_status values vs. reject-and-abort | Pattern 5 | If user prefers strict mode, might need a config flag; deferred unless plan-discussion surfaces this |
| A4 | The user accepts a one-time `/scout-setup` re-prompt after `LEGACY_DATA_DIRS` deletion | Pattern 4 | If user has many legacy dirs in the chain not auto-detected by setup-prompt, manual path entry needed |
| A5 | `pytest` is the chosen test framework (per success criterion "`python3 -m pytest tests/test_migration.py`") | Pattern 3 | If unittest is preferred, test shape changes but coverage is equivalent |
| A6 | The `companies_per_day=5` choice (matching `templates/config.json`) is preferred over `=8` | CON-06 in Phase Requirements table | If user wants 8, change templates/config.json (not the skill docs); decision deferred to plan-discussion |
| A7 | `runs.jsonl` is append-only forever in v0.4 (rotation/size policy is a v0.5+ concern) | Pitfall calls + Open Questions | After ~12 months of daily runs at ~30 companies × 5 providers, file grows to ~50–200 MB — readable by Python but slow with `tail`/`grep`. Phase 2 writer can add `ats.runs_log_max_mb` config knob preemptively. |
| A8 | The `_write_tracker` rebuild-everything pattern is acceptable to inherit unchanged (CON-20 deferred to Phase 5) | Pattern 2 + Pitfall 1 | Existing users with custom tracker columns 15+ silently lose them on first v0.4 append. Mitigation: release-notes warning. |
| A9 | The `tests/__init__.py` should exist (vs pure pytest auto-discovery) | Project structure recommendation | Either works; pytest finds tests in either case |
| A10 | The migration test runs from project root (`cd job-scout-plugin && pytest`) and `tests/` is a sibling of `scripts/` | Pattern 3 sibling-bootstrap | If pytest invoked from inside `tests/`, `Path(__file__).parent.parent` adjustment needed |
| A11 | `MASTER_TARGETS_VERSION` is a breadcrumb only (not used for migration dispatch) — the user accepts this stays cosmetic | Pattern 1 | If user wants version-aware migration NOW, the plan changes shape (add migration registry) |

**Items requiring user confirmation (high-priority):** A2, A3, A4, A6, A11. Discuss in plan-discussion before locking.

## Open Questions

1. **`STATUS_VALUES` membership** — does the user use any status outside the 7 canonical members?
   - What we know: schema.py:30 says `application_status` is "free text — 'Applied 2026-03-12 / no response', 'Dead', etc." That implies `Dead` and `Applied` exist; the others are defaults.
   - What's unclear: whether `Hold`, `Ghosted`, `On Ice`, etc. are statuses the user types.
   - Recommendation: surface the proposed 7-member set in plan-discussion; ask for additions/removals before locking.

2. **`companies_per_day` canonical value** — 5 (template) or 8 (skill prompt)?
   - What we know: template ships 5; skill says 8; doc says "5 vs 8."
   - What's unclear: what value the user actually wants in their daily run.
   - Recommendation: ask in plan-discussion. Default to 5 (template-aligned) unless user explicitly says 8.

3. **`LEGACY_DATA_DIRS` deletion impact** — is the user currently on a legacy path?
   - What we know: state.json exists for the user (per `CLAUDE.md` "user data lives in `~/Documents/JobSearch/`"); legacy fallback wouldn't fire.
   - What's unclear: whether any other developer or test environment relies on the legacy chain.
   - Recommendation: confirm in plan-discussion. If user has multiple machines or others use the plugin, consider adding the setup-prompt step (Pattern 4) BEFORE deleting the chain — not after.

4. **`runs.jsonl` rotation policy for Phase 2** — Phase 1 only ensures the file exists.
   - What we know: file will accrue ~1 line/day in v0.4. Per-(company, provider) telemetry per DSP-07 makes each line ~5–20 KB.
   - What's unclear: at what size does `tail -100 runs.jsonl | jq` get slow? When does the file need rotation?
   - Recommendation: defer to Phase 2 writer plan. Phase 1 lands `runs.jsonl` path only. Suggest config knob `ats.runs_log_max_mb: 50` (rotate to `runs.jsonl.1` when exceeded) — Phase 2 implements; Phase 1 can prepare config schema.

5. **`tests/__init__.py` — empty file or absent?**
   - What we know: pytest auto-discovers either way.
   - What's unclear: whether the project wants `tests/` to be importable as a package (allowing `from tests.fixtures import ...`).
   - Recommendation: include an empty `tests/__init__.py` for forward-compat; cost is one empty file.

6. **`ats_raw/` per-provider subdir granularity in `file-contract.md`** — should the entry list `daily/<DATE>/ats_raw/<provider>/` or just `daily/<DATE>/ats_raw/`?
   - What we know: Phase 4 fills it; Phase 1 lands the directory.
   - Recommendation: Phase 1 lists `daily/<DATE>/ats_raw/` only (the directory). Phase 4 may extend with per-provider subdir notation if/when it's clear that subdirs are needed (vs flat layout `ats_raw/<company>__<provider>.json`).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.8+ | All scripts (existing) | ✓ | 3.13.5 (Homebrew) | — |
| pandas | `validate_data`, `consolidate_targets`, `mine_connections`, test | ✓ on dev | 2.2.3 (system); 3.0.2 latest | `pip install pandas` (in venv per new install hint) |
| openpyxl | `tracker_utils` | ✗ on default `python3`; needs `pip install openpyxl` in venv or via `--user` | 3.1.5 latest | Install required for any tracker work |
| pytest | `tests/test_migration.py` | ✗ | 9.0.3 latest / 8.4.2 stable | `pipx install pytest` OR `pip install pytest` in project venv |
| pipx | install-hint recommendation | ✓ via Homebrew | 1.11.1 | `python3 -m venv` is the alternative path |
| Homebrew | Python install on macOS | ✓ | 5.1.5 | — |
| `git` | commit phase artifacts | (assumed available; project is a git repo) | — | — |

**Missing dependencies with no fallback:**
- None. Every Phase 1 dep has either an idempotent installer or a documented alternative.

**Missing dependencies with fallback:**
- `pytest`: required for SCH-05 verification. User must install before running the test (recommended: `pipx install pytest` for a global CLI; or `python3 -m venv .venv && pip install pytest pandas openpyxl` for a project venv).
- `openpyxl`: required for any tracker rewrite test path. The current dev machine doesn't have it in default `python3`; install as part of test prereqs.

**Caveat:** The `python3` on PATH (`/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`) is NOT the Homebrew-managed Python (`/opt/homebrew/opt/python@3.13/Frameworks/Python.framework/Versions/3.13/bin/python3.13`). Two Python 3.13 installations coexist. The plan should specify which Python the test runs against — recommend Homebrew's (it's the one Homebrew-installed `pipx` will inject into venvs). [VERIFIED: `which python3` and `brew list --formula | grep python` both confirm.]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 (stable) or 9.0.3 (latest) — either works |
| Config file | None — pytest auto-discovers `tests/test_*.py`; no `pytest.ini` needed in Phase 1 |
| Quick run command | `python3 -m pytest tests/test_migration.py -x -v` |
| Full suite command | `python3 -m pytest tests/ -v` (Phase 1 has only one test file; this is a forward-looking command) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCH-03 | Schema bump to v=4; new cols added | unit | `pytest tests/test_migration.py::test_schema_version_is_v4 -v` | ❌ Wave 0 |
| SCH-03 | All v3 rows preserved through migration | unit | `pytest tests/test_migration.py::test_all_v3_rows_preserved -v` | ❌ Wave 0 |
| SCH-03 | New v=4 cols present and empty | unit | `pytest tests/test_migration.py::test_new_v4_columns_present_and_empty -v` | ❌ Wave 0 |
| SCH-03 | User-added column survives | unit | `pytest tests/test_migration.py::test_user_added_column_survives -v` | ❌ Wave 0 |
| SCH-03 | v0.3-shape reader can parse v=4 CSV | unit | `pytest tests/test_migration.py::test_v3_reader_can_parse_v4_csv -v` | ❌ Wave 0 |
| SCH-04 | Tracker `source` + `ats_provider` cols extend `HEADERS` | manual | Visual: open xlsx after running `tracker_utils.py append` against test rows | manual-only — no test for tracker xlsx format in Phase 1 |
| SCH-01 | `runs.jsonl` exists after `validate_data.py` | smoke | `python3 scripts/validate_data.py /tmp/test_dir && test -f /tmp/test_dir/runs.jsonl` | manual-only |
| SCH-02 | `daily/<DATE>/ats_raw/` exists after `validate_data.ensure_today_subdirs` | smoke | `python3 scripts/validate_data.py ensure-today /tmp/test_dir 2026-04-28 && test -d /tmp/test_dir/daily/2026-04-28/ats_raw` | manual-only |
| SCH-05 | Migration test passes against fixture | unit | `pytest tests/test_migration.py -x` | ❌ Wave 0 (this IS the new test file) |
| SCH-06 | `file-contract.md` has both new entries | manual-only | Visual diff review | manual-only |
| CON-01 | `consolidate()` does not crash on v=3 file | smoke | `python3 scripts/consolidate_targets.py --output /tmp/m.csv --files tests/fixtures/master_targets_v3.csv && echo OK` | manual-only |
| CON-02 | Unknown `application_status` warns + coerces | unit | Add `tests/test_status_validation.py::test_unknown_status_coerces_to_active` (optional Phase 1 extension) | ❌ Wave 0 (optional — recommend including) |
| CON-03 | `mine_connections.py` warns on header-fallback | manual | Run against a Spanish-localized fixture; check stderr | manual-only |
| CON-04 | All 4 import-handlers updated | manual | `grep -rn "break-system-packages" scripts/` returns 0 lines | grep-based, automatable |
| CON-05 | `LEGACY_DATA_DIRS` removed | manual | `grep -n "LEGACY_DATA_DIRS" scripts/state.py` returns 0 lines | grep-based, automatable |
| CON-06 | `companies_per_day` default cited only in template | manual | `grep -rn "companies_per_day.*default" skills/` returns 0 inline-number quotes | grep-based, automatable |
| CON-07 | state.json perms are 0o600; STATE_DIR is 0o700 | smoke | `python3 scripts/state.py write /tmp/x && stat -f %p ~/.job-scout/state.json` (macOS) | smoke-testable |

### Sampling Rate

- **Per task commit:** `python3 -m pytest tests/test_migration.py -x` (under 2 seconds)
- **Per wave merge:** `python3 -m pytest tests/ -v` + the grep checks for CON-04, CON-05, CON-06 (under 5 seconds)
- **Phase gate:** Full pytest suite green + all manual-grep checks pass + manual smoke test of `python3 scripts/validate_data.py <data_dir>` produces both `runs.jsonl` and migrates a v=3 master_targets in place

### Wave 0 Gaps

- [ ] `tests/__init__.py` — empty marker (recommended)
- [ ] `tests/test_migration.py` — covers SCH-05 (and by extension SCH-03)
- [ ] `tests/fixtures/master_targets_v3.csv` — checked-in fixture
- [ ] `tests/conftest.py` — NOT needed for Phase 1 (`tmp_path` is built-in)
- [ ] Optional: `tests/test_status_validation.py` — recommend including for CON-02 confidence
- [ ] Framework install: documented in test file docstring; not enforced by code

## Security Domain

> Security enforcement is implicit (no `security_enforcement: false` in `.planning/config.json`). The phase is mostly schema/path mechanics, but CON-07 specifically lands a security control.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth in Phase 1; ATS APIs are public read-only (Phase 2+) |
| V3 Session Management | no | No sessions |
| V4 Access Control | yes | CON-07: `state.json` 0o600 + `~/.job-scout/` 0o700 prevents other local users from reading the data_dir path |
| V5 Input Validation | yes | CON-02: STATUS_VALUES enum validates tracker append input; CON-03: header-detection validates LinkedIn export shape |
| V6 Cryptography | no | No crypto in Phase 1; resume PDF + connections CSV stay plaintext (CON-18/19 are deferred to Phase 6) |

### Known Threat Patterns for Phase 1

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Local user reads `~/.job-scout/state.json` to discover data_dir → reads resume + connections.csv | Information Disclosure | `os.chmod(STATE_PATH, 0o600)` + `os.chmod(STATE_DIR, 0o700)` (CON-07) |
| Magic-string `application_status` value silently re-includes a `Dead` company | Tampering (data integrity) | `STATUS_VALUES` frozenset + warn-and-coerce on tracker append (CON-02) |
| LinkedIn-export-format change silently drops 3 connections per run | Tampering (data integrity) | Header-detection warning + post-skip column validation + abort-on-unrecognizable (CON-03) |
| `pip install --break-system-packages` advice corrupts user's system Python | Denial-of-Service (against the user's OS) | Switch to venv/`--user`/`pipx` install hints (CON-04) |
| `LEGACY_DATA_DIRS` fallback picks the wrong directory on a multi-data-dir machine | Information Disclosure (writes to wrong dir) | Delete the fallback chain (CON-05) |

## Sources

### Primary (HIGH confidence)

- **`scripts/schema.py`** — read 2026-04-27 — `MASTER_TARGETS_COLUMNS` (11 cols), `MASTER_TARGETS_VERSION = 3`, `TRACKER_COLUMNS` (14 cols), `TRACKER_JSON_KEYS`, `TRACKER_COL_WIDTHS`, helper factories.
- **`scripts/state.py`** — read 2026-04-27 — `LEGACY_DATA_DIRS` at lines 32-36, `resolve_data_dir` walks the chain at lines 78-81. No chmod calls in `write_state`.
- **`scripts/validate_data.py`** — read 2026-04-27 — `validate_master_targets` at lines 63-93 (column-by-column additive). Install-hint at line 29 currently `--break-system-packages`.
- **`scripts/tracker_utils.py`** — read 2026-04-27 — `_write_tracker` rebuilds workbook at lines 264-315; `load_tracker` pads short rows to `len(HEADERS)` at lines 132-136; `append_rows` doesn't currently validate status. CON-13 / CON-14 / CON-20 are inherited (not Phase 1 scope).
- **`scripts/consolidate_targets.py`** — read 2026-04-27 — Line 270 IS guarded: `len(master[master['already_applied'].str.upper() == 'Y']) if 'already_applied' in master.columns else 0`. **CON-01 audit was stale** — the KeyError can no longer happen. Reframe as "delete dead code, lines 269-272."
- **`scripts/mine_connections.py`** — read 2026-04-27 — `detect_header_rows` falls through to `(3, 'latin-1')` at line 45 with no warning.
- **`templates/config.json`** — read 2026-04-27 — `companies_per_day: 5` at line 32.
- **`skills/job-scout/references/file-contract.md`** — read 2026-04-27 — table format for "persistent files" and "per-run output" sections.
- **`skills/scout-run/SKILL.md`** — read 2026-04-27 — `companies_per_day` quoted as "default 8" at line 73.
- **`skills/job-scout/references/search-config.md`** — read 2026-04-27 — `companies_per_day` "default 8 in older configs, default 5 in template" at line 43.
- **pip index versions probes (2026-04-28):** `pytest` → 9.0.3 latest / 8.4.2 stable; `pandas` → 3.0.2 latest / 2.2.3 installed; `openpyxl` → 3.1.5 latest.
- **Homebrew** confirmed available: `brew --version` → 5.1.5; `pipx` available via brew at 1.11.1.

### Secondary (MEDIUM confidence)

- **PEP 668 + pipx vs venv** — [PEP 668 spec](https://peps.python.org/pep-0668/), [pythonspeed.com on externally-managed environments](https://pythonspeed.com/articles/externally-managed-environment-pep-668/), [pydevtools handbook](https://pydevtools.com/handbook/explanation/what-is-pep-668/), [Jeff Geerling blog](https://www.jeffgeerling.com/blog/2023/how-solve-error-externally-managed-environment-when-installing-pip3/) — confirms `pipx` for CLIs, `venv` for project libraries, `--user` install bypasses PEP 668 on Homebrew Python where the user-site is not "externally managed."
- **pytest 8.x vs 9.x** — [pytest changelog](https://docs.pytest.org/en/stable/changelog.html) (not deeply reviewed; either works for the test shape).
- **CONCERNS.md, PITFALLS.md** — internal research docs; some claims (CON-01) corrected against actual current source.

### Tertiary (LOW confidence — needs validation)

- **`STATUS_VALUES` member set** — proposed 7 canonical statuses derived from common job-search vocabulary, not from observed user data. Confirm in plan-discussion.
- **Existing tracker xlsx files in user's wild — column count beyond 14** — not directly observed; CON-20's framing assumes some users have manual extras. Mitigation is release-notes warning, not code.
- **macOS chmod-on-NFS edge case** — theoretical (no user reports). Best-effort `_harden_perms` helper covers it.

## Metadata

**Confidence breakdown:**

- **Standard stack (pytest, pandas, openpyxl):** HIGH — versions verified against pip index 2026-04-28; all already established in project (except pytest, which has a clear install path).
- **Architecture (column-by-column additive migration; tracker rebuild handles row padding; STATUS_VALUES frozenset):** HIGH — patterns directly readable in current source; recommendations require no new logic.
- **Pitfalls:** HIGH — five of six are direct reads of existing source code (e.g., `_write_tracker` line 293 `if col > len(HEADERS): break`); one (chmod-on-NFS) is theoretical but mitigated.
- **CON-01 reframing (`already_applied` is guarded, not crashing):** HIGH — verified by direct read of `consolidate_targets.py:270`.
- **`LEGACY_DATA_DIRS` deletion strategy:** MEDIUM — recommendation is sound but assumption A4 (user accepts one-time re-prompt) is unconfirmed.
- **`STATUS_VALUES` member set:** MEDIUM — assumption A2/A3 require user input.
- **`companies_per_day` chosen value (5 vs 8):** LOW — assumption A6; ask in plan-discussion.

**Research date:** 2026-04-27
**Valid until:** 2026-05-27 (30 days; the underlying tools — pandas, pytest, openpyxl — are stable and unlikely to ship breaking changes in that window)

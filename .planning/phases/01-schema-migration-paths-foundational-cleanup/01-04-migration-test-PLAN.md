---
phase: 01-schema-migration-paths-foundational-cleanup
plan: 04
type: tdd
wave: 2
depends_on: [01-01-schema-PLAN]
files_modified:
  - tests/__init__.py
  - tests/test_migration.py
  - tests/fixtures/master_targets_v3.csv
autonomous: true
requirements: [SCH-05]

must_haves:
  truths:
    - "tests/fixtures/master_targets_v3.csv contains 3 realistic v=3-shape rows including one with a user-added 'my_notes' column at the end"
    - "tests/test_migration.py round-trips the v=3 fixture through validate_master_targets() and asserts: (a) all rows preserved, (b) new v=4 columns present and empty, (c) user-added column survives at the end, (d) a v=3-shape reader can still parse the v=4 CSV"
    - "python3 -m pytest tests/test_migration.py exits 0 against a v=4 schema.py (Plan 01 prerequisite)"
    - "Phase 1 wave-2 grep gates all pass: zero --break-system-packages refs in scripts/, zero LEGACY_DATA_DIRS in scripts/, single companies_per_day numeric default site"
  artifacts:
    - path: tests/__init__.py
      provides: empty package marker for forward-compat
    - path: tests/test_migration.py
      provides: pytest module with 4 test functions covering SCH-05 + a v=4 sanity check
      exports: ["test_schema_version_is_v4", "test_all_v3_rows_preserved", "test_new_v4_columns_present_and_empty", "test_user_added_column_survives", "test_v3_reader_can_parse_v4_csv"]
    - path: tests/fixtures/master_targets_v3.csv
      provides: realistic v=3 fixture (11 canonical cols + 1 user-added col, 3 rows)
  key_links:
    - from: tests/test_migration.py
      to: scripts/schema.py + scripts/validate_data.py
      via: "sibling-bootstrap sys.path.insert(0, str(SCRIPTS_DIR))"
      pattern: "sys\\.path\\.insert.*SCRIPTS_DIR"
    - from: tests/test_migration.py::migrated_data_dir fixture
      to: tests/fixtures/master_targets_v3.csv
      via: "shutil.copy(FIXTURE, data_dir / 'master_targets.csv'); validate_master_targets(str(data_dir))"
      pattern: "validate_master_targets"
---

<objective>
Ship the SCH-05 migration round-trip test as a TDD plan (one feature, one file, RED→GREEN→REFACTOR semantics). The test file is the carved-out exception to the v0.4 "no test suite" rule per CLAUDE.md and PROJECT.md.

The test asserts the v=3→v=4 migration is correct against a checked-in fixture:
1. All v=3 rows preserved (zero data loss)
2. New v=4 columns (`ats_slug_confidence`, `last_ats_hit_date`) present and empty
3. User-added columns survive at the end (the `validate_master_targets` "extras at end" rule)
4. A v=3-shape reader can parse the migrated v=4 CSV (proves "extra columns tolerated" without depending on git history)

Plus one sanity assertion: `MASTER_TARGETS_VERSION == 4` (catches a Plan 01 regression).

This plan is `wave: 2` and `depends_on: [01-01-schema-PLAN]` because the test imports `MASTER_TARGETS_VERSION` and exercises `validate_master_targets` — both must be at v=4 shape before the test passes (GREEN). Run order: Plan 01 lands schema → this plan's tests pass → grep checks confirm whole-phase cleanup.

This plan also folds in a final phase-wide grep gate as Task 3 — the bookkeeping check that all 4 install-hint sites are clean (Plan 01's two + Plan 02's two) and other CON-* grep-verifiable invariants hold. This task makes the phase-completion verifier reliable — it's a 5-second smoke test that catches any straggling `--break-system-packages` reference or lingering `LEGACY_DATA_DIRS` symbol that slipped between parallel plans.

Output: `tests/__init__.py`, `tests/test_migration.py`, `tests/fixtures/master_targets_v3.csv`, all green via `python3 -m pytest tests/test_migration.py -v`. Phase-wide grep gate green.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/01-schema-migration-paths-foundational-cleanup/01-RESEARCH.md
@.planning/phases/01-schema-migration-paths-foundational-cleanup/01-01-schema-PLAN.md
@.planning/phases/01-schema-migration-paths-foundational-cleanup/01-02-cleanup-PLAN.md
@CLAUDE.md
@scripts/schema.py
@scripts/validate_data.py

<interfaces>
<!-- Contracts the test exercises (post-Plan-01). -->

From scripts/schema.py (after Plan 01):
```python
MASTER_TARGETS_VERSION = 4
MASTER_TARGETS_COLUMNS = [
    "company_name", "industry", "career_page_url", "ats_provider", "ats_board_url",
    "connection_names", "linkedin_connection_count", "application_status",
    "fit_notes", "last_checked", "data_source",
    "ats_slug_confidence",   # NEW v=4
    "last_ats_hit_date",     # NEW v=4
]
```

From scripts/validate_data.py (Plan 01 unchanged the migration logic; only added validate_runs_log + ensure_today_subdirs):
```python
def validate_master_targets(data_dir: str) -> tuple[bool, str]:
    """Adds any missing column from MASTER_TARGETS_COLUMNS with empty default.
    Reorders to canonical-first; user-added columns end up at the end.
    Never deletes rows. Returns (True, '...added missing columns: [...]') or (True, 'ok').
    """
```

V=3 fixture shape (what we generate at tests/fixtures/master_targets_v3.csv):
- 11 canonical v=3 columns + 1 user-added `my_notes` column
- 3 rows: (a) populated, (b) sparse, (c) edge-case
</interfaces>
</context>

<feature>
  <name>SCH-05 v=3 → v=4 migration round-trip test</name>
  <files>tests/__init__.py, tests/test_migration.py, tests/fixtures/master_targets_v3.csv</files>
  <behavior>
    `python3 -m pytest tests/test_migration.py -v` runs 5 tests, all PASS, against a v=4 schema.py:

    1. `test_schema_version_is_v4` — sanity check that `MASTER_TARGETS_VERSION == 4`. RED if Plan 01 didn't bump.
    2. `test_all_v3_rows_preserved` — fixture has 3 rows; after migration the CSV still has 3 rows; every fixture `company_name` appears exactly once in the migrated file.
    3. `test_new_v4_columns_present_and_empty` — `ats_slug_confidence` and `last_ats_hit_date` columns exist; both empty for every row (use `.fillna("").eq("").all()` per Pitfall 5 in 01-RESEARCH.md, defensive against pandas 2.x vs 3.x NA differences).
    4. `test_user_added_column_survives` — `my_notes` column is present in the migrated CSV AND is the LAST column (canonical-first ordering rule from `validate_master_targets`).
    5. `test_v3_reader_can_parse_v4_csv` — synthesize a v=3 reader inline via `pd.read_csv(usecols=lambda c: c in v3_columns)`; assert it reads exactly the 11 canonical v=3 columns and all 3 rows. Proves "extra columns tolerated" without git history.

    All tests use the `migrated_data_dir` pytest fixture (defined in test_migration.py) which copies the fixture to tmp_path/data, runs `validate_master_targets`, and yields the path.
  </behavior>
  <implementation>
    ## RED phase

    1. Create `tests/__init__.py` (empty file, package marker for forward-compat per Open Question 5).

    2. Create `tests/fixtures/master_targets_v3.csv` with this exact content:
       ```csv
       company_name,industry,career_page_url,ats_provider,ats_board_url,connection_names,linkedin_connection_count,application_status,fit_notes,last_checked,data_source,my_notes
       Stripe,Fintech,https://stripe.com/jobs,greenhouse,https://boards.greenhouse.io/stripe,Alice Smith (Eng Manager); Bob Jones (Director),5,,Strong commerce fit,2026-04-20,linkedin_connections,investigate Q3
       lululemon,Retail,https://careers.lululemon.com,workday,https://lululemon.wd5.myworkdayjobs.com/careers,,3,Applied 2026-03-12 / no response,Tech leadership ladder is real,2026-04-15,user_csv,
       Acme,,,,,,0,Dead,passed on 2026-Q1,2026-01-10,scout_discovered,
       ```

       (11 v=3 cols + 1 user-added `my_notes` col. Three rows: populated, sparse, edge-case.)

    3. Create `tests/test_migration.py` with the full skeleton from 01-RESEARCH.md Pattern 3 (lines 339-435), including the module docstring naming the fixture rationale, the sibling-bootstrap, the `migrated_data_dir` pytest fixture, and the 5 test functions.

    4. Confirm RED: WITHOUT Plan 01 landed (i.e., schema.py still at v=3), `pytest tests/test_migration.py::test_schema_version_is_v4` fails with `assert MASTER_TARGETS_VERSION == 4` and the column-presence tests fail because the columns aren't in the constant. Skip this step if Plan 01 is already merged at run time — RED is automatic in TDD.

    Commit: `test(01-04): add failing migration round-trip test for v=3 -> v=4 schema bump`

    ## GREEN phase

    5. Plan 01 has already landed by Wave 2. Run `python3 -m pytest tests/test_migration.py -v` from repo root. All 5 tests pass.

    6. If a test fails, the failure is a Plan 01 regression (not a test bug). Surface the failure to the orchestrator; do NOT modify the test to make it pass.

    Commit: `feat(01-04): migration round-trip test passes against v=4 schema`

    ## REFACTOR phase

    7. None expected. The test file is small (~80 lines) and one-shot. If a future phase extends it (e.g., v=4→v=5 migration), the existing 5 tests stay; new ones get added.

    ## File contents

    **tests/__init__.py** — empty file (zero bytes).

    **tests/test_migration.py:**

    ```python
    """
    Migration round-trip test for the v3->v4 master_targets.csv schema bump.

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

    Test prereqs: a Python environment with pandas + openpyxl + pytest installed.
    Recommended setup:
      python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate
      pip install pytest pandas openpyxl

    Run:
      python3 -m pytest tests/test_migration.py -v
    """
    import os
    import shutil
    import sys
    from pathlib import Path

    import pandas as pd
    import pytest

    # Bootstrap project scripts on sys.path (sibling-script pattern from CONVENTIONS)
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    SCRIPTS_DIR = PROJECT_ROOT / "scripts"
    sys.path.insert(0, str(SCRIPTS_DIR))

    from schema import MASTER_TARGETS_COLUMNS, MASTER_TARGETS_VERSION  # noqa: E402
    from validate_data import validate_master_targets  # noqa: E402

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
        """Sanity: the schema constant is at v=4 (catches a Plan 01 regression)."""
        assert MASTER_TARGETS_VERSION == 4


    def test_all_v3_rows_preserved(migrated_data_dir):
        """SCH-05 assertion (a): all v3 rows preserved."""
        df = pd.read_csv(migrated_data_dir / "master_targets.csv")
        fixture_df = pd.read_csv(FIXTURE)
        assert len(df) == len(fixture_df), "row count changed during migration"
        for name in fixture_df["company_name"]:
            assert (df["company_name"] == name).sum() == 1, f"company {name!r} lost or duplicated"


    def test_new_v4_columns_present_and_empty(migrated_data_dir):
        """SCH-05 assertion (b): new columns present and empty."""
        df = pd.read_csv(migrated_data_dir / "master_targets.csv")
        assert "ats_slug_confidence" in df.columns
        assert "last_ats_hit_date" in df.columns
        # fillna("").eq("").all() defensive against pandas 2.x vs 3.x NA differences
        assert df["ats_slug_confidence"].fillna("").eq("").all()
        assert df["last_ats_hit_date"].fillna("").eq("").all()


    def test_user_added_column_survives(migrated_data_dir):
        """User-added columns must survive at the end (validate_master_targets rule)."""
        df = pd.read_csv(migrated_data_dir / "master_targets.csv")
        assert "my_notes" in df.columns, "user-added column was dropped"
        assert df.columns[-1] == "my_notes", \
            f"my_notes should be last column; got {df.columns[-1]!r}"


    def test_v3_reader_can_parse_v4_csv(migrated_data_dir):
        """SCH-05 assertion (c): v0.3 code path can still read the v=4 CSV without crash.

        Simulate v0.3 by reading only the v=3 canonical columns explicitly.
        pandas tolerates extra columns; this proves the contract.
        """
        v3_columns = [
            "company_name", "industry", "career_page_url", "ats_provider", "ats_board_url",
            "connection_names", "linkedin_connection_count", "application_status",
            "fit_notes", "last_checked", "data_source",
        ]
        df_v3_view = pd.read_csv(
            migrated_data_dir / "master_targets.csv",
            usecols=lambda c: c in v3_columns,
        )
        assert sorted(df_v3_view.columns) == sorted(v3_columns)
        fixture_df = pd.read_csv(FIXTURE)
        assert len(df_v3_view) == len(fixture_df)
    ```

    **tests/fixtures/master_targets_v3.csv** — exactly the 4-line CSV shown in step 2 above.
  </implementation>
</feature>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create tests/__init__.py + tests/fixtures/master_targets_v3.csv</name>
  <files>tests/__init__.py, tests/fixtures/master_targets_v3.csv</files>
  <read_first>
    - .planning/phases/01-schema-migration-paths-foundational-cleanup/01-RESEARCH.md (Pattern 3 — fixture content lines 443-451)
  </read_first>
  <behavior>
    - `tests/__init__.py` exists and is empty (zero bytes).
    - `tests/fixtures/master_targets_v3.csv` exists with exactly 4 lines (1 header + 3 data rows).
    - Header row contains 12 columns: 11 canonical v=3 + `my_notes` at the end.
    - All 3 rows have valid CSV (no unbalanced quotes; semicolons used INSIDE quoted fields for `connection_names`).
  </behavior>
  <action>
    Run from repo root:

    ```bash
    mkdir -p tests/fixtures
    ```

    Create `tests/__init__.py` with empty content (use the Write tool with content `""`).

    Create `tests/fixtures/master_targets_v3.csv` with EXACTLY this content (4 lines, no trailing blank line):

    ```csv
    company_name,industry,career_page_url,ats_provider,ats_board_url,connection_names,linkedin_connection_count,application_status,fit_notes,last_checked,data_source,my_notes
    Stripe,Fintech,https://stripe.com/jobs,greenhouse,https://boards.greenhouse.io/stripe,Alice Smith (Eng Manager); Bob Jones (Director),5,,Strong commerce fit,2026-04-20,linkedin_connections,investigate Q3
    lululemon,Retail,https://careers.lululemon.com,workday,https://lululemon.wd5.myworkdayjobs.com/careers,,3,Applied 2026-03-12 / no response,Tech leadership ladder is real,2026-04-15,user_csv,
    Acme,,,,,,0,Dead,passed on 2026-Q1,2026-01-10,scout_discovered,
    ```

    Note the `connection_names` cell for Stripe contains semicolons (per existing convention in scripts/schema.py:28) — these are INSIDE the comma-delimited cell because the cell does NOT contain commas, so no quoting is required by RFC 4180.

    The `lululemon` row's `application_status` is `Applied 2026-03-12 / no response` — note this contains a slash and a space, which is part of the existing schema.py example free-text format. Both are CSV-safe (no commas, no quotes).
  </action>
  <verify>
    <automated>cd /Users/rmoore/Workspaces/job-scout-plugin && test -f tests/__init__.py && test ! -s tests/__init__.py && test -f tests/fixtures/master_targets_v3.csv && test "$(wc -l < tests/fixtures/master_targets_v3.csv | tr -d ' ')" = "4" && head -1 tests/fixtures/master_targets_v3.csv | grep -q "company_name" && head -1 tests/fixtures/master_targets_v3.csv | grep -q "my_notes" && python3 -c "import csv; rows = list(csv.reader(open('tests/fixtures/master_targets_v3.csv'))); assert len(rows) == 4, f'rows={len(rows)}'; assert len(rows[0]) == 12, f'cols={len(rows[0])}'; assert rows[0][-1] == 'my_notes'; assert rows[1][0] == 'Stripe'; assert rows[2][0] == 'lululemon'; assert rows[3][0] == 'Acme'; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `test -f tests/__init__.py` passes AND `test ! -s tests/__init__.py` passes (file exists and is empty)
    - `test -f tests/fixtures/master_targets_v3.csv` passes
    - `wc -l < tests/fixtures/master_targets_v3.csv` returns `4` (1 header + 3 rows; trailing newline counts the last row)
    - `head -1 tests/fixtures/master_targets_v3.csv | tr ',' '\n' | wc -l` returns `12`
    - The 12th header is `my_notes`
    - The 3 data rows have company_name `Stripe`, `lululemon`, `Acme` in that order
    - The verify command prints `OK`
  </acceptance_criteria>
  <done>
    `tests/__init__.py` (empty marker) and `tests/fixtures/master_targets_v3.csv` (12-column, 3-row v=3 fixture) exist. `csv.reader` parses the fixture cleanly with 4 rows of 12 columns each.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Write tests/test_migration.py covering all 5 SCH-05 assertions</name>
  <files>tests/test_migration.py</files>
  <read_first>
    - tests/fixtures/master_targets_v3.csv (created in Task 1)
    - scripts/schema.py (after Plan 01 — confirms MASTER_TARGETS_VERSION == 4 and the new columns)
    - scripts/validate_data.py (the existing `validate_master_targets` function — Plan 01 did NOT modify it)
    - .planning/phases/01-schema-migration-paths-foundational-cleanup/01-RESEARCH.md (Pattern 3 — full test skeleton at lines 314-435)
  </read_first>
  <behavior>
    - `python3 -m pytest tests/test_migration.py -v` (in an env with pandas + pytest) runs 5 tests, all PASS.
    - Each test has a clear docstring naming the SCH-05 assertion (or sanity check) it covers.
    - The `migrated_data_dir` fixture isolates each test in its own `tmp_path` — no cross-test pollution.
  </behavior>
  <action>
    Use the Write tool to create `tests/test_migration.py` with the full content from the `<implementation>` section above (the exact module docstring + imports + sibling-bootstrap + `FIXTURE` constant + `migrated_data_dir` fixture + 5 test functions).

    Do NOT alter the test code — copy verbatim from the spec. The implementation block in this plan is the canonical source.

    After writing, run pytest to confirm GREEN:

    ```bash
    cd /Users/rmoore/Workspaces/job-scout-plugin && python3 -m pytest tests/test_migration.py -v
    ```

    If pytest fails on `import pandas` or `import pytest`, the runner is in the wrong Python environment. Per CON-04 install hint, the user installs deps via:
    ```bash
    python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate && pip install pytest pandas openpyxl
    ```
    Then re-runs the pytest command.

    If `test_schema_version_is_v4` fails, Plan 01 has not landed correctly — surface to the orchestrator; do NOT modify the test to compensate.
  </action>
  <verify>
    <automated>cd /Users/rmoore/Workspaces/job-scout-plugin && test -f tests/test_migration.py && python3 -c "import ast; ast.parse(open('tests/test_migration.py').read())" && grep -q "def test_schema_version_is_v4" tests/test_migration.py && grep -q "def test_all_v3_rows_preserved" tests/test_migration.py && grep -q "def test_new_v4_columns_present_and_empty" tests/test_migration.py && grep -q "def test_user_added_column_survives" tests/test_migration.py && grep -q "def test_v3_reader_can_parse_v4_csv" tests/test_migration.py && grep -q "def migrated_data_dir" tests/test_migration.py && python3 -m pytest tests/test_migration.py -v 2>&1 | tail -20</automated>
  </verify>
  <acceptance_criteria>
    - `test -f tests/test_migration.py` passes
    - `python3 -c "import ast; ast.parse(open('tests/test_migration.py').read())"` exits 0 (file is valid Python)
    - `grep -q "def test_schema_version_is_v4" tests/test_migration.py` returns 0
    - `grep -q "def test_all_v3_rows_preserved" tests/test_migration.py` returns 0
    - `grep -q "def test_new_v4_columns_present_and_empty" tests/test_migration.py` returns 0
    - `grep -q "def test_user_added_column_survives" tests/test_migration.py` returns 0
    - `grep -q "def test_v3_reader_can_parse_v4_csv" tests/test_migration.py` returns 0
    - `grep -q "def migrated_data_dir" tests/test_migration.py` returns 0 (the pytest fixture)
    - `grep -q "sys.path.insert(0, str(SCRIPTS_DIR))" tests/test_migration.py` returns 0 (sibling-bootstrap)
    - `python3 -m pytest tests/test_migration.py -v` exits 0 with "5 passed" in the output
  </acceptance_criteria>
  <done>
    `tests/test_migration.py` exists, parses as valid Python, and `pytest tests/test_migration.py -v` reports 5 passed. The migration round-trip is locked behind the test for every future schema change.
  </done>
</task>

<task type="auto">
  <name>Task 3: Phase-wide grep gate (verifies all wave-1 + wave-2 invariants hold)</name>
  <files>(no file edits — verification-only task)</files>
  <read_first>
    - All Plan 01 + Plan 02 + Plan 03 acceptance criteria (the grep checks they each define)
  </read_first>
  <behavior>
    A single shell pipeline confirms every grep-verifiable Phase 1 invariant:
    - Zero `--break-system-packages` references in `scripts/` (CON-04, all 4 sites — Plans 01 + 02)
    - Zero `LEGACY_DATA_DIRS` references in `scripts/` (CON-05 — Plan 02)
    - Zero numeric `companies_per_day` defaults outside `templates/config.json` (CON-06 — Plan 03)
    - `MASTER_TARGETS_VERSION = 4` in schema.py (SCH-03 — Plan 01)
    - `STATUS_VALUES` defined in schema.py (CON-02 — Plan 01)
    - `_harden_perms` defined in state.py (CON-07 — Plan 02)
    - `validate_runs_log` defined in validate_data.py (SCH-01 — Plan 01)
    - `ensure_today_subdirs` defined in validate_data.py (SCH-02 — Plan 01)
    - `runs.jsonl` referenced in file-contract.md (SCH-06 — Plan 03)
    - `ats_raw/` referenced in file-contract.md (SCH-06 — Plan 03)
    - "Existing data directory check" in scout-setup/SKILL.md (CON-05 user-facing — Plan 03)
  </behavior>
  <action>
    Run this verification pipeline. It is the canonical phase-completion gate for Phase 1:

    ```bash
    cd /Users/rmoore/Workspaces/job-scout-plugin

    # CON-04: zero break-system-packages refs in scripts/
    test "$(grep -rc 'break-system-packages' scripts/ 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')" = "0" || { echo "FAIL: break-system-packages still present in scripts/"; exit 1; }

    # CON-05: LEGACY_DATA_DIRS gone from state.py
    test "$(grep -c LEGACY_DATA_DIRS scripts/state.py 2>/dev/null)" = "0" || { echo "FAIL: LEGACY_DATA_DIRS still in state.py"; exit 1; }

    # CON-06: no inline numeric companies_per_day defaults outside templates/
    test "$(grep -cE 'companies_per_day.*[0-9]' skills/scout-run/SKILL.md skills/job-scout/references/search-config.md 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')" = "0" || { echo "FAIL: numeric companies_per_day default still in skill docs"; exit 1; }
    grep -q '"companies_per_day": 5' templates/config.json || { echo "FAIL: companies_per_day not at canonical 5 in template"; exit 1; }

    # SCH-03 + CON-02 + Plan 01 schema bumps
    grep -q "MASTER_TARGETS_VERSION = 4" scripts/schema.py || { echo "FAIL: schema not bumped to v=4"; exit 1; }
    grep -q "ats_slug_confidence" scripts/schema.py || { echo "FAIL: ats_slug_confidence missing"; exit 1; }
    grep -q "last_ats_hit_date" scripts/schema.py || { echo "FAIL: last_ats_hit_date missing"; exit 1; }
    grep -q "STATUS_VALUES = frozenset" scripts/schema.py || { echo "FAIL: STATUS_VALUES missing"; exit 1; }

    # CON-07: _harden_perms in state.py
    grep -q "def _harden_perms" scripts/state.py || { echo "FAIL: _harden_perms missing"; exit 1; }
    grep -q "_harden_perms(STATE_PATH, 0o600)" scripts/state.py || { echo "FAIL: 0o600 chmod missing"; exit 1; }
    grep -q "_harden_perms(STATE_DIR, 0o700)" scripts/state.py || { echo "FAIL: 0o700 chmod missing"; exit 1; }

    # SCH-01 + SCH-02: new validators in validate_data.py
    grep -q "def validate_runs_log" scripts/validate_data.py || { echo "FAIL: validate_runs_log missing"; exit 1; }
    grep -q "def ensure_today_subdirs" scripts/validate_data.py || { echo "FAIL: ensure_today_subdirs missing"; exit 1; }

    # SCH-06: file-contract.md path entries
    grep -q "runs.jsonl" skills/job-scout/references/file-contract.md || { echo "FAIL: runs.jsonl not in file-contract.md"; exit 1; }
    grep -q "ats_raw/" skills/job-scout/references/file-contract.md || { echo "FAIL: ats_raw/ not in file-contract.md"; exit 1; }

    # CON-05 user-facing: legacy-dir prompt in scout-setup
    grep -q "Existing data directory check" skills/scout-setup/SKILL.md || { echo "FAIL: legacy-dir prompt missing in scout-setup"; exit 1; }

    # SCH-05: pytest passes
    python3 -m pytest tests/test_migration.py -v 2>&1 | tail -3 | grep -q "5 passed" || { echo "FAIL: migration tests not all passing"; exit 1; }

    # CON-01: no dead already_applied refs in consolidate_targets
    test "$(grep -c already_applied scripts/consolidate_targets.py 2>/dev/null)" = "0" || { echo "FAIL: already_applied still in consolidate_targets.py"; exit 1; }

    # CON-03: header-detection guard in mine_connections
    grep -q "WARNING: detect_header_rows fell through" scripts/mine_connections.py || { echo "FAIL: WARNING missing in mine_connections.py"; exit 1; }
    grep -q "has_name_col" scripts/mine_connections.py || { echo "FAIL: post-skip column validation missing"; exit 1; }

    echo "PHASE 1 GATE: ALL CHECKS PASSED"
    ```

    The script exits 0 with `PHASE 1 GATE: ALL CHECKS PASSED` on success. On any failure, exits 1 with a specific FAIL line — the orchestrator can see which invariant broke.

    This task does NOT modify any file — it only verifies. If a check fails, surface to the orchestrator; the failing plan needs revision (route through `/gsd-plan-phase` revision mode against that plan's must_haves).
  </action>
  <verify>
    <automated>cd /Users/rmoore/Workspaces/job-scout-plugin && bash -c 'set -e; test "$(grep -rc break-system-packages scripts/ 2>/dev/null | awk -F: "{s+=\$2} END {print s+0}")" = "0"; test "$(grep -c LEGACY_DATA_DIRS scripts/state.py 2>/dev/null)" = "0"; test "$(grep -cE "companies_per_day.*[0-9]" skills/scout-run/SKILL.md skills/job-scout/references/search-config.md 2>/dev/null | awk -F: "{s+=\$2} END {print s+0}")" = "0"; grep -q "\"companies_per_day\": 5" templates/config.json; grep -q "MASTER_TARGETS_VERSION = 4" scripts/schema.py; grep -q "ats_slug_confidence" scripts/schema.py; grep -q "STATUS_VALUES = frozenset" scripts/schema.py; grep -q "def _harden_perms" scripts/state.py; grep -q "def validate_runs_log" scripts/validate_data.py; grep -q "def ensure_today_subdirs" scripts/validate_data.py; grep -q "runs.jsonl" skills/job-scout/references/file-contract.md; grep -q "ats_raw/" skills/job-scout/references/file-contract.md; grep -q "Existing data directory check" skills/scout-setup/SKILL.md; python3 -m pytest tests/test_migration.py 2>&1 | tail -3 | grep -q "5 passed"; test "$(grep -c already_applied scripts/consolidate_targets.py 2>/dev/null)" = "0"; grep -q "WARNING: detect_header_rows fell through" scripts/mine_connections.py; echo "PHASE 1 GATE OK"'</automated>
  </verify>
  <acceptance_criteria>
    - The single bash pipeline above prints `PHASE 1 GATE OK` and exits 0
    - Specifically: 0 break-system-packages, 0 LEGACY_DATA_DIRS, 0 inline numeric companies_per_day defaults, schema at v=4, all helpers defined, 5 pytest tests passing, no `already_applied` references, mine_connections WARNING string present
  </acceptance_criteria>
  <done>
    Phase 1's grep-verifiable invariants are all green. The phase is ready for verifier hand-off and the next phase planning trigger.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| User's existing v=3 master_targets.csv → validate_master_targets migration | Untrusted column shape (user may have added arbitrary columns; 11 canonical may not all be present in some edge case) crosses into the v=4 CSV |
| Test fixture → CI / dev environment | Fixture is checked-in; tampering shows as a diff, not a runtime concern |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-01 | Tampering (data integrity during migration) | validate_master_targets on user's CSV | mitigate | The 5 pytest assertions verify zero data loss against a realistic fixture (3 rows, 12 cols incl. user-added). RED before Plan 01 lands; GREEN after. Future schema changes that break this contract fail the test before reaching users (SCH-05). |
| T-04-02 | Tampering (test bypass) | Test could be modified to make a regression pass | accept | The test file is small, reviewed at git-diff time, and the 5 assertions trace 1:1 to SCH-05 sub-criteria. A reviewer would see test edits in any PR. Phase 1's no-test-suite carve-out is explicit — no broader bypass surface exists. |
| T-04-03 | Repudiation (silent regression in another plan) | Plans 01-03 invariants drift after merge | mitigate | Task 3 grep gate catches every invariant in 5 seconds. Run as the final verifier step before phase close. |
</threat_model>

<verification>
After all 3 tasks complete:

```bash
# Test green
python3 -m pytest tests/test_migration.py -v   # 5 passed

# Phase-wide gate
bash -c '...'   # Task 3's verify command — prints "PHASE 1 GATE OK"
```

Both must succeed.
</verification>

<success_criteria>
- `tests/__init__.py` (empty) and `tests/fixtures/master_targets_v3.csv` (4 lines, 12 cols) exist
- `tests/test_migration.py` has 5 test functions named per the spec; all imports resolve via sibling-bootstrap
- `python3 -m pytest tests/test_migration.py -v` reports `5 passed`
- The phase-wide grep gate (Task 3) exits 0 with `PHASE 1 GATE OK`
- Every Plan 01–04 grep-verifiable invariant from `must_haves.truths` is observable in the codebase
</success_criteria>

<output>
After completion, create `.planning/phases/01-schema-migration-paths-foundational-cleanup/01-04-SUMMARY.md` summarizing the test fixture, the 5 test functions, and the phase-wide grep gate result. Note any deps that were missing from the dev environment (pytest / pandas) so the user can install them with the v0.4 hint.
</output>

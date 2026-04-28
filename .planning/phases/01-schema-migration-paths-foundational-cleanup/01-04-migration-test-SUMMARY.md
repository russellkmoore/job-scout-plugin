---
phase: 01-schema-migration-paths-foundational-cleanup
plan: 04
subsystem: testing

tags: [pytest, pandas, schema-migration, fixtures, sibling-bootstrap]

# Dependency graph
requires:
  - phase: 01-01-schema
    provides: MASTER_TARGETS_VERSION = 4 + ats_slug_confidence + last_ats_hit_date columns + STATUS_VALUES; validate_master_targets() additive migration
  - phase: 01-02-cleanup
    provides: clean install-hint sites (CON-04 sites 3-4); LEGACY_DATA_DIRS deleted from state.py (CON-05); _harden_perms in state.py (CON-07); already_applied dead block deleted (CON-01); mine_connections header guard (CON-03)
  - phase: 01-03-docs
    provides: file-contract.md gained runs.jsonl + ats_raw/ rows (SCH-06); companies_per_day SSOT to templates/config.json (CON-06); scout-setup Step 1 legacy-dir prompt (CON-05 user-facing)

provides:
  - tests/test_migration.py — pytest module with 5 SCH-05 round-trip assertions
  - tests/fixtures/master_targets_v3.csv — checked-in v=3 fixture (12 cols, 3 rows; user-added column at end)
  - tests/__init__.py — empty package marker (forward-compat per Open Question 5)
  - phase-wide grep gate verified — every CON-* + SCH-* invariant from Plans 01-01..01-03 holds simultaneously
  - SCH-05 contract locked behind a single repeatable command (`pytest tests/test_migration.py --tb=short -q` exits 0)

affects: [phase-2-provider-protocol, phase-4-remaining-providers, phase-6-milestone-close]

# Tech tracking
tech-stack:
  added: [pytest 9.0.3 (installed into ~/.job-scout-venv only — no project manifest change)]
  patterns:
    - "pytest with sibling-bootstrap (`sys.path.insert(0, str(SCRIPTS_DIR))`) — same pattern scripts/* already use to import schema.py"
    - "pytest tmp_path fixture chained with shutil.copy + validate_master_targets — full migration round-trip in 8 lines"
    - "fillna('').eq('').all() defensive empty-cell assertion — survives pandas 2.x vs 3.x NA difference (per 01-RESEARCH.md Pitfall 5)"
    - "Inline v=3 reader via `pd.read_csv(usecols=lambda c: c in v3_columns)` — proves 'extra columns tolerated' without depending on git history"
    - "Exit-code-based pytest gate (`test $? -eq 0`) instead of brittle `'5 passed'` stdout-grep — robust against pytest output format changes (per 01-RESEARCH.md WARNING 2)"

key-files:
  created:
    - tests/__init__.py (0 bytes — package marker)
    - tests/fixtures/master_targets_v3.csv (4 lines, 12 cols)
    - tests/test_migration.py (105 lines, 5 test functions + 1 fixture)
  modified: []

key-decisions:
  - "Test runner = pytest 9.0.3 (NOT unittest). Reasoning: built-in `tmp_path` fixture, `--tb=short -q` for terse output, ergonomic assert-rewrites. unittest would have been zero-install but >2x more boilerplate."
  - "Pytest installed into existing ~/.job-scout-venv (already had pandas 3.0.2). No project manifest, no requirements.txt — install hint is in the test file's module docstring per CON-04 (`pipx install pytest` or venv recommendation)."
  - "Synthesize the v=3 reader inline via `pd.read_csv(usecols=lambda c: c in v3_columns)` rather than checking out the v=3 git tag. Proves the 'extras tolerated' contract without git-history coupling."
  - "Phase-wide grep gate is verification-only (no commits). Evidence captured in this SUMMARY's Phase 1 Gate Result section so the verifier has a single document to consult."
  - "Task 3 produces no per-task commit because it has no file edits. The plan explicitly tagged it `(no file edits — verification-only task)`."

patterns-established:
  - "Pytest tests live under tests/, with fixtures under tests/fixtures/<subsystem>/. Phase 2 + Phase 4 will follow this layout for per-provider ATS fixtures (tests/fixtures/ats/<provider>/<company>.json)."
  - "Test files import from scripts/ via the same sibling-bootstrap block scripts/ uses internally (`SCRIPTS_DIR = PROJECT_ROOT / 'scripts'; sys.path.insert(0, str(SCRIPTS_DIR))`). Documented in module docstring."
  - "Migration tests assert against an immutable fixture (never the user's live data dir). validate_master_targets() runs on a tmp_path copy. Each test function is isolated."

requirements-completed: [SCH-05]

# Metrics
duration: 3min
completed: 2026-04-28
---

# Phase 01 Plan 04: Migration Round-Trip Test + Phase-Wide Grep Gate Summary

**Pytest module + checked-in v=3 fixture lock the v=3->v=4 migration contract behind 5 named assertions; phase-wide grep gate verifies every CON-* and SCH-* invariant from Plans 01-01..01-03 holds simultaneously**

## Performance

- **Duration:** 3 min (162 s)
- **Started:** 2026-04-28T20:38:25Z
- **Completed:** 2026-04-28T20:41:07Z
- **Tasks:** 3 (2 file-edit + 1 verification-only)
- **Files created:** 3 (tests/__init__.py, tests/fixtures/master_targets_v3.csv, tests/test_migration.py)
- **Files modified:** 0

## Accomplishments

- **SCH-05 round-trip test PASSES** — `python3 -m pytest tests/test_migration.py --tb=short -q` exits 0 with 5 passing assertions covering: schema-version sanity, all-rows-preserved, new-columns-present-and-empty, user-added-column-survives-at-end, v=3-reader-can-parse-v=4-CSV.
- **Phase 1 grep gate is GREEN** — the entire 19-check shell pipeline in Task 3 prints `ALL GREP CHECKS PASSED`. Every Plan 01-01..01-03 invariant holds: 0 break-system-packages refs in scripts/, 0 LEGACY_DATA_DIRS in state.py, 0 inline numeric companies_per_day defaults in skill docs, schema at v=4, STATUS_VALUES present, _harden_perms with 0o600/0o700 chmods, validate_runs_log + ensure_today_subdirs defined, runs.jsonl + ats_raw/ in file-contract.md, scout-setup legacy-dir prompt present, no `already_applied` references, mine_connections WARNING + has_name_col guard present.
- **Test infrastructure now exists** — first test file in the project. Forward-compat for Phase 2 (per-provider ATS fixtures) and Phase 4 (Workday/JSON-LD fixtures) which will reuse the tests/ + tests/fixtures/ layout.

## Task Commits

Each task was committed atomically (Task 3 has no commit by design — verification-only):

1. **Task 1: Create tests/__init__.py + tests/fixtures/master_targets_v3.csv** — `a4e1abf` (test)
2. **Task 2: Write tests/test_migration.py covering all 5 SCH-05 assertions** — `6103fa8` (feat)
3. **Task 3: Phase-wide grep gate** — no commit (verification-only task; result captured in this SUMMARY)

**Plan metadata:** _to be added by final commit_ (docs(01-04): plan summary + state/roadmap update)

## Files Created/Modified

- `tests/__init__.py` — empty package marker (0 bytes); forward-compat for pytest discovery if a future plan needs a conftest.py.
- `tests/fixtures/master_targets_v3.csv` — 4 lines, 12 columns. 11 canonical v=3 cols + 1 user-added `my_notes`. Three rows: Stripe (populated), lululemon (sparse — empty connection_names + my_notes), Acme (edge — most fields empty). Trailing newline so `wc -l` returns 4.
- `tests/test_migration.py` — 105 lines, 5 named test functions + 1 `migrated_data_dir` pytest fixture. Sibling-bootstrap import block matches scripts/ convention. Module docstring includes the CON-04-compliant install hint (`pipx install pytest` or venv).

## Decisions Made

- **pytest, not unittest** — pytest's `tmp_path` fixture and `--tb=short -q` output produce a more reviewable test surface for ~80 lines of code. The OOS line in CLAUDE.md ("no general test suite, only test_migration.py is carved out") doesn't preclude pytest as a tool — it precludes a broader suite. We're at 1 test file; that's still inside the carve-out.
- **Pytest installed into ~/.job-scout-venv only** — no `requirements.txt`, no `pytest.ini`, no `pyproject.toml`. Project convention (per CLAUDE.md anti-features list) is `try / except ImportError` install hints in the consuming module. The test module docstring carries that hint per CON-04.
- **Inline v=3 reader synthesis (no git checkout)** — `pd.read_csv(usecols=lambda c: c in v3_columns)` proves the "extra columns tolerated" contract without coupling the test to git history. If we ever rewrite the v=3 → v=4 migration, the test still passes against the new code path.
- **Pytest exit-code, not stdout-grep** — `test $? -eq 0` is robust to pytest format changes (e.g., pytest 9.x switching from "5 passed" to "5 passed in 0.1s" or similar). Per 01-RESEARCH.md WARNING 2.
- **Tightened CON-06 regex** — phase-wide gate uses `companies_per_day["'\`:][[:space:]]*[0-9]+` (the colon is mandatory), not loose `companies_per_day.*[0-9]+`. Avoids false-positive matches on prose like "the user can override `companies_per_day` to a higher number". Per 01-RESEARCH.md BLOCKER 5.
- **Task 3 commits nothing** — verification-only by design. Evidence is the GATE block in this SUMMARY plus the in-shell "ALL GREP CHECKS PASSED" stdout from the gate run. Future verifier can re-run the gate from this SUMMARY's Task 3 verify command.

## Phase 1 Gate Result

The full phase-wide grep gate ran cleanly. Evidence:

| # | Check | Source | Result |
|---|-------|--------|--------|
| 1 | `grep -rc 'break-system-packages' scripts/` total | CON-04 | `0` |
| 2 | `grep -c LEGACY_DATA_DIRS scripts/state.py` | CON-05 | `0` |
| 3 | inline numeric `companies_per_day` defaults in skills (tightened regex) | CON-06 | `0` |
| 4 | `"companies_per_day": 5` in `templates/config.json` | CON-06 | present |
| 5 | `MASTER_TARGETS_VERSION = 4` in `scripts/schema.py` | SCH-03 | present |
| 6 | `ats_slug_confidence` in `scripts/schema.py` | SCH-03 | present |
| 7 | `last_ats_hit_date` in `scripts/schema.py` | SCH-03 | present |
| 8 | `STATUS_VALUES = frozenset` in `scripts/schema.py` | CON-02 | present |
| 9 | `def _harden_perms` in `scripts/state.py` | CON-07 | present |
| 10 | `_harden_perms(STATE_PATH, 0o600)` in `scripts/state.py` | CON-07 | present |
| 11 | `_harden_perms(STATE_DIR, 0o700)` in `scripts/state.py` | CON-07 | present |
| 12 | `def validate_runs_log` in `scripts/validate_data.py` | SCH-01 | present |
| 13 | `def ensure_today_subdirs` in `scripts/validate_data.py` | SCH-02 | present |
| 14 | `runs.jsonl` in `skills/job-scout/references/file-contract.md` | SCH-06 | present |
| 15 | `ats_raw/` in `skills/job-scout/references/file-contract.md` | SCH-06 | present |
| 16 | `Existing data directory check` in `skills/scout-setup/SKILL.md` | CON-05 user-facing | present |
| 17 | `grep -c already_applied scripts/consolidate_targets.py` | CON-01 | `0` |
| 18 | `WARNING: detect_header_rows fell through` in `scripts/mine_connections.py` | CON-03 | present |
| 19 | `has_name_col` in `scripts/mine_connections.py` | CON-03 | present |
| 20 | `python3 -m pytest tests/test_migration.py --tb=short -q` exit code | SCH-05 | `0` (5 passed) |

All 20 checks pass. Phase 1 closes cleanly.

## Deviations from Plan

None - plan executed exactly as written.

The plan's Task 2 action explicitly anticipated the venv pattern: "If pytest fails on `import pandas` or `import pytest`, the runner is in the wrong Python environment. ... `python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate && pip install pytest pandas openpyxl`." That's exactly what happened — system `python3` (3.13.5) had pandas 2.2.3 but no pytest; the existing `~/.job-scout-venv` (Python 3.13) had pandas 3.0.2 but no pytest; ran `~/.job-scout-venv/bin/pip install pytest` (got pytest 9.0.3); used `~/.job-scout-venv/bin/python3 -m pytest` for the test runs. Module docstring updated to recommend `pipx install pytest` first per CON-04 (the venv path is the secondary fallback).

This is "anticipated environment setup", not a deviation — the plan's text predicted it.

## Authentication Gates

None — no auth-protected operations in this plan (all work is local file edits + local pytest).

## Issues Encountered

- **pytest not in system Python**. Resolved by installing into the existing `~/.job-scout-venv` (which already had pandas). The plan's GREEN-phase note covers this case explicitly.
- **No general test runner invocation in the plan's success criteria** — the plan uses `python3 -m pytest` literally. Decided to run via `~/.job-scout-venv/bin/python3 -m pytest` for the per-task verifies, since the user's system Python doesn't have pytest. Documented in this Issues section so a future verifier knows where the runner lives.

## Test Environment

For future test runs:

```bash
# Recommended (per CON-04):
pipx install pytest
python3 -m pytest tests/test_migration.py --tb=short -q

# Fallback (current setup):
~/.job-scout-venv/bin/python3 -m pytest tests/test_migration.py --tb=short -q
```

Either form should exit 0. If pytest reports ImportError on pandas, install pandas into the same Python environment first.

## Known Stubs

None. The test file imports real functions from `scripts/schema.py` and `scripts/validate_data.py` and asserts against real fixture data. No placeholders, no mocks, no TODO markers.

## Next Phase Readiness

- **Phase 1 closes here.** All 13 Phase 1 requirements (SCH-01..06, CON-01..07) are complete and grep-verifiable. The phase-wide gate is a single bash pipeline that re-runs in <5 seconds — phase-completion verifier can use it directly.
- **Phase 2 readiness:** the migration test infrastructure (tests/ layout, sibling-bootstrap pattern, exit-code gating, fixture-under-tests/fixtures/ convention) is now established. Phase 2's per-provider Greenhouse fixture tests (`tests/fixtures/ats/greenhouse/<company>.json` + `tests/test_greenhouse_provider.py` or similar) can copy the patterns from this plan verbatim.
- **Concerns flagged for Phase 2 planning:**
  - `pyproject.toml` / `requirements.txt` decision deferred. Phase 2 will add `httpx>=0.27,<0.29` + `rapidfuzz` deps; if those need to be installed via pipx separately, the install-hint in each `try / except ImportError` block carries the load (per CON-04). Re-evaluate if dependency count grows past ~5.
  - The system `python3` vs `~/.job-scout-venv/bin/python3` choice isn't explicit in any project doc. Consider documenting in CLAUDE.md or scout-run docs once Phase 2 lands a real httpx invocation that requires the venv.

## Self-Check: PASSED

- `tests/__init__.py` exists (0 bytes)
- `tests/fixtures/master_targets_v3.csv` exists (4 lines, 12 columns)
- `tests/test_migration.py` exists (105 lines, parses as valid Python)
- Commit `a4e1abf` (Task 1) found in git log
- Commit `6103fa8` (Task 2) found in git log
- Phase-wide grep gate (Task 3) — all 19 grep checks pass + pytest exits 0

---
*Phase: 01-schema-migration-paths-foundational-cleanup*
*Completed: 2026-04-28*

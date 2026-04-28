---
phase: 01-schema-migration-paths-foundational-cleanup
verified: 2026-04-28T13:55:00Z
status: gaps_found
score: 6/7 success criteria verified (13/13 REQ-IDs technically present, but SC-4 wiring gap means SCH-02 is plumbed but not invoked at runtime)
overrides_applied: 0
gaps:
  - truth: "Running /scout-run on a fresh setup produces empty <data_dir>/runs.jsonl AND <data_dir>/daily/<DATE>/ats_raw/ directory before any ATS code executes (SC-4)"
    status: partial
    reason: "runs.jsonl half passes (validate_runs_log is in main()'s validator list, line 177 of validate_data.py). The ats_raw/ half FAILS at runtime: validate_data.py:ensure_today_subdirs and the `ensure-today` CLI subcommand exist and work in isolation, but skills/scout-run/SKILL.md NEVER calls `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_data.py ensure-today \"<data_dir>\" \"<TODAY>\"`. The plumbing exists; the wiring does not. Phase 2 covers writing TO ats_raw/ (SC-2 of Phase 2), but Phase 2's SCs do not commit to ensuring the directory's existence at /scout-run start, so this is NOT deferred-by-roadmap — it is a Phase 1 gap."
    artifacts:
      - path: skills/scout-run/SKILL.md
        issue: "Step 0 (line 32) calls bare `validate_data.py \"<data_dir>\"` which routes through main()'s validator list. ensure_today_subdirs is intentionally NOT in that list (the comment at validate_data.py:138 says it must run after <TODAY> is resolved, i.e., as a separate ensure-today subcommand call). Step 4 (lines 47-51) computes <TODAY> but never calls ensure-today afterward."
    missing:
      - "After computing <TODAY> in Step 4 of skills/scout-run/SKILL.md, add a one-line invocation: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_data.py ensure-today \"<data_dir>\" \"<TODAY>\"` so the daily/<DATE>/ats_raw/ directory is guaranteed to exist before any ATS provider code (Phase 2+) writes a payload into it."
      - "Optionally, add a self-check assertion at the bottom of Step 4 confirming os.path.isdir(daily/<TODAY>/ats_raw) so a missed wiring fails loudly instead of silently flowing into Phase 2's writer."
deferred: []
---

# Phase 1: Schema migration + paths + foundational cleanup Verification Report

**Phase Goal:** master_targets.csv, tracker xlsx, and runs.jsonl upgraded to v0.4 shape with zero data loss; v3→v4 migration locked behind a fixture test; foundational tech-debt items in scripts/ fixed in the same commits that touch those files.
**Verified:** 2026-04-28T13:55:00Z
**Status:** gaps_found (1 partial truth — SC-4 ats_raw/ wiring missing in scout-run/SKILL.md)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| SC-1 | v0.3 master_targets.csv upgrades to v=4 in place; new cols added; rows + user cols preserved | VERIFIED | scripts/validate_data.py:68-98 column-by-column additive logic; behavioral spot-check on tests/fixtures/master_targets_v3.csv (3 rows, my_notes user col) confirms `my_notes` preserved at last position, ats_slug_confidence + last_ats_hit_date present and empty, all 3 rows preserved. |
| SC-2 | Tracker xlsx gains Source + ATS Provider columns; existing rows back-compatible | VERIFIED | scripts/schema.py:103-121 TRACKER_COLUMNS = 16 entries with "Source" + "ATS Provider"; behavioral spot-check (manual v=3 14-col xlsx → append → load) confirms auto-widening to 16 cols, existing Acme row preserved with empty Source/ATS Provider, new Stripe row populated correctly. |
| SC-3 | pytest tests/test_migration.py passes; asserts (a) rows preserved, (b) new cols empty, (c) v=3 reader can parse v=4 | VERIFIED | `~/.job-scout-venv/bin/python3 -m pytest tests/test_migration.py --tb=short -q` → 5 passed in 0.27s. tests/test_migration.py:61-105 contains all four required assertions (schema_version_is_v4, all_v3_rows_preserved, new_v4_columns_present_and_empty, user_added_column_survives, v3_reader_can_parse_v4_csv). |
| SC-4 | /scout-run on fresh setup produces empty runs.jsonl AND daily/<DATE>/ats_raw/ before any ATS code executes | **PARTIAL** | runs.jsonl: validate_data.py:177 has `("runs_log", validate_runs_log)` in main()'s validator list — verified by /tmp/td_phase1_verify spot-check (runs.jsonl created automatically). **ats_raw/: FAILS at runtime.** validate_data.py:136-144 has ensure_today_subdirs and the `ensure-today` subcommand works in isolation, but skills/scout-run/SKILL.md:32 calls only `validate_data.py "<data_dir>"` — never calls `ensure-today`. Spot-check: bare validate_data.py creates runs.jsonl but NOT daily/2026-04-28/ats_raw/. |
| SC-5 | file-contract.md is the only doc that lists runs.jsonl + daily/<DATE>/ats_raw/ as canonical paths | VERIFIED | `grep -rn "runs.jsonl\|ats_raw" skills/` returns 2 hits, both in skills/job-scout/references/file-contract.md (lines 36, 52). No other skill/reference doc treats them as canonical. |
| SC-6 | consolidate no KeyError; tracker validates application_status; mine_connections logs warning on Spanish export. **(SC-6 wording overridden during planning: "rejects" → "warn-and-pass-through" per locked decision; see verification_context note.)** | VERIFIED (with override-aware reading) | (a) consolidate_targets.py:0 matches for `already_applied` — dead block deleted; line 274-278 has the CON-01 comment. (b) tracker_utils.py:208-228 calls normalize_application_status; behavioral spot-check with status='dad' produces stderr WARNING "preserved as 'dad'" AND writes 'dad' verbatim to xlsx (NOT 'Active') — confirms the e0863b2 regression fix. (c) mine_connections.py:49-58 has the WARNING for header-detection fall-through; lines 82-108 add post-skip column validation that aborts with ERROR if columns missing. |
| SC-7 | All ImportError hints recommend pipx/venv (not --break-system-packages); state.json 0o600 + dir 0o700; LEGACY_DATA_DIRS removed (with /scout-setup migration prompt); single canonical companies_per_day | VERIFIED | (a) `grep -rn "break-system-packages" scripts/ --include="*.py"` returns 0 matches across all 4 .py files (validate_data.py:29-34, tracker_utils.py:31-36, consolidate_targets.py:26-32, mine_connections.py:25-31 all use venv hint). (b) state.py:60-61, 75, 84 all chmod to 0o600/0o700; helper _harden_perms (lines 29-43) handles OSError gracefully. (c) `grep -n "LEGACY_DATA_DIRS" scripts/state.py` returns 0; user-facing migration prompt at skills/scout-setup/SKILL.md:33-49 detects 3 legacy dirs and calls `state.py write` inline. (d) `grep -rEn 'companies_per_day["\`][[:space:]]*[0-9]+' skills/ templates/` returns ONLY templates/config.json:32 (= 5); skills/scout-run/SKILL.md:73 and search-config.md:43 use prose pointer. The skills/scout-setup/SKILL.md:117 occurrence "companies_per_day: 5" is summary prose with `:` separator — outside the tightened verify regex per the locked CON-06 decision. |

**Score:** 6/7 truths verified (1 partial — SC-4 ats_raw/ wiring)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| scripts/schema.py | v=4 columns, STATUS_VALUES, normalize_application_status, 16-col tracker | VERIFIED | MASTER_TARGETS_VERSION=4, MASTER_TARGETS_COLUMNS = 13 entries (incl. ats_slug_confidence + last_ats_hit_date), TRACKER_COLUMNS = 16 entries (incl. Source + ATS Provider), STATUS_VALUES = frozenset of 9, normalize_application_status returns (s, True) for unknowns (warn-and-pass-through). |
| scripts/validate_data.py | validate_runs_log + ensure_today_subdirs + ensure-today CLI; venv install hint | VERIFIED | Both functions exist (lines 122-144); `("runs_log", validate_runs_log)` in main() validator list (line 177); `ensure-today` CLI subcommand at lines 154-162; pandas install hint at lines 29-34 uses venv. |
| scripts/tracker_utils.py | normalize_application_status integration + 16-col rows + venv hint | VERIFIED | Imports normalize_application_status (line 50); append_rows wires status validation at lines 208-228 (warn-and-pass-through, no rewrite); row_list builds 16 entries (lines 230-247) with source + ats_provider at positions 15/16; openpyxl install hint at lines 31-36 uses venv. |
| scripts/state.py | LEGACY_DATA_DIRS removed; perm hardening 0o600/0o700; venv hint not needed (no third-party imports) | VERIFIED | No LEGACY_DATA_DIRS references; _harden_perms helper (lines 29-43); both read_state and write_state apply 0o600/0o700; resolve_data_dir returns "" if not configured (CON-05 acknowledgment at lines 46-49). |
| scripts/consolidate_targets.py | Dead `already_applied` block deleted; venv install hint | VERIFIED | 0 matches for `already_applied`; CON-01 comment at lines 274-276 documents the deletion; pandas install hint at lines 26-32 uses venv. |
| scripts/mine_connections.py | WARNING + post-skip column validation; venv install hint | VERIFIED | WARNING on header-detection fall-through (lines 49-58); post-skip column validation (lines 82-108) aborts with ERROR if no name+company column found; pandas install hint at lines 25-31 uses venv. |
| skills/job-scout/references/file-contract.md | runs.jsonl + ats_raw/ as canonical paths | VERIFIED | runs.jsonl row at line 36; daily/<DATE>/ats_raw/ row at line 52; both cross-reference the validators that create them. |
| skills/scout-run/SKILL.md | No inline numeric companies_per_day default; ensure-today wiring | PARTIAL | Inline numeric default removed at line 73 (uses prose `(see companies_per_day in templates/config.json)`); BUT ensure-today subcommand never invoked — Step 4 computes <TODAY> but Step 0/1/2/3/4 never calls validate_data.py ensure-today. |
| skills/job-scout/references/search-config.md | No inline numeric companies_per_day default | VERIFIED | Line 43 uses prose pointer; tightened regex returns 0 matches. |
| skills/scout-setup/SKILL.md | Step 1 legacy-dir migration prompt | VERIFIED | New question 4 at lines 33-49 detects 3 legacy paths, prompts reuse, calls state.py write inline. |
| templates/config.json | companies_per_day = 5 (untouched, canonical) | VERIFIED | Line 32: `"companies_per_day": 5,` — sole numeric default site. |
| tests/test_migration.py | 5 round-trip assertions on v=3→v=4 fixture | VERIFIED | All 5 tests pass; assertions match SC-3 wording verbatim. |
| tests/fixtures/master_targets_v3.csv | 3 v=3 rows + 1 user-added column | VERIFIED | 3 rows (Stripe, lululemon, Acme), 11 canonical v=3 cols + my_notes user col. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| scripts/tracker_utils.py | scripts/schema.py | `from schema import normalize_application_status` | WIRED | Import + call at lines 50, 220. |
| scripts/validate_data.py | scripts/schema.py | `from schema import MASTER_TARGETS_COLUMNS, TRACKER_COLUMNS` | WIRED | Import at lines 42-46; consumed at lines 74, 85. |
| scripts/consolidate_targets.py | scripts/schema.py | `from schema import MASTER_TARGETS_COLUMNS as MASTER_COLUMNS` | WIRED | Import at line 40. |
| skills/scout-run/SKILL.md | scripts/validate_data.py | `python3 .../validate_data.py "<data_dir>"` (Step 0) | WIRED (incomplete) | Bare validate call wires runs_log creation; missing ensure-today wiring (see SC-4 gap). |
| skills/scout-run/SKILL.md | scripts/validate_data.py | `python3 .../validate_data.py ensure-today "<data_dir>" "<TODAY>"` (Step 4 should call this) | **NOT_WIRED** | scout-run/SKILL.md never calls the ensure-today subcommand. ats_raw/ is never created at run start. |
| skills/scout-setup/SKILL.md | scripts/state.py | `python3 .../state.py write "<data_dir>"` (legacy reuse path) | WIRED | Inline call at line 45 of scout-setup. |
| tests/test_migration.py | scripts/validate_data.py | `from validate_data import validate_master_targets` | WIRED | Import + use at line 40, 51. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|---------------------|--------|
| validate_master_targets() | df (DataFrame) | pd.read_csv on master_targets.csv at line 78; column-by-column addition at lines 85-88 | YES — preserves existing rows + appends new columns + preserves user extras | FLOWING |
| append_rows() | row_dict (per row) | json.load at line 182; status flows through normalize_application_status at line 220; row_list built at lines 230-247 | YES — produces 16-col rows; status preserved verbatim on unknown values; warn fires; new cols populated from input | FLOWING |
| validate_runs_log() | path | os.path.isfile + open(path, 'a').close() at lines 130-131 | YES — creates empty file (idempotent touch) | FLOWING |
| ensure_today_subdirs() | today_dir | os.makedirs at line 143 | YES at script-level — but **NOT invoked from scout-run/SKILL.md**, so the data flow stops at the script's CLI boundary | DISCONNECTED at the skill layer |

### Behavioral Spot-Checks

| Behavior | Command / Test | Result | Status |
|----------|----------------|--------|--------|
| pytest tests/test_migration.py passes | `~/.job-scout-venv/bin/python3 -m pytest tests/test_migration.py --tb=short -q` | "5 passed in 0.27s" | PASS |
| normalize_application_status warn-and-pass-through (regression check from commit e0863b2) | `python3 -c "...assert normalize_application_status('Stale — Verify') == ('Stale — Verify', True)..."` | "warn-and-pass-through verified" | PASS |
| SC-1 end-to-end: v=3 fixture → migration → user col preserved | Inline pandas script: load fixture, call validate_master_targets, assert columns + my_notes at end | All assertions pass; my_notes at last col; 3 rows preserved; new cols empty | PASS |
| SC-2 end-to-end: v=3 14-col xlsx → append → 16-col xlsx | Inline openpyxl script: build 14-col xlsx with Acme row, run append_rows with new Stripe row | 16-col xlsx; Acme preserved (Source/ATS Provider empty); Stripe Source='ats:greenhouse' | PASS |
| SC-6 CON-02: status='dad' typo preserved + warned | Inline script: append row with status='dad' | stderr emits WARNING; xlsx stores 'dad' verbatim (NOT 'Active') | PASS |
| SC-4 (a): bare validate_data.py creates runs.jsonl | `validate_data.py /tmp/td_phase1_verify` then `test -f /tmp/td_phase1_verify/runs.jsonl` | runs.jsonl created (size 0) | PASS |
| SC-4 (b): bare validate_data.py creates daily/<TODAY>/ats_raw/ | After bare validate, `test -d /tmp/td_phase1_verify/daily/2026-04-28/ats_raw` | NO — directory not created (ensure_today_subdirs is NOT in main()'s validator list, by design) | **FAIL** |
| SC-4 (b) — alternate path: ensure-today subcommand works when called directly | `validate_data.py ensure-today /tmp/td_phase1_verify 2026-04-28` then test -d ats_raw | YES — directory created | PASS (script-level) — but call site missing in scout-run/SKILL.md |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| SCH-01 | runs.jsonl ensured at /scout-run start | SATISFIED | validate_data.py:122-133 + main() validator list line 177; behavioral spot-check confirmed at runtime. |
| SCH-02 | daily/<DATE>/ats_raw/ ensured before Pass 1 ATS writes | **PARTIALLY SATISFIED** | Plumbing complete (validate_data.py:136-144 + ensure-today CLI at lines 154-162), but the call site in skills/scout-run/SKILL.md is missing. Will fail at runtime once Phase 2 starts writing ATS payloads. |
| SCH-03 | MASTER_TARGETS_VERSION → 4; ats_slug_confidence + last_ats_hit_date columns | SATISFIED | scripts/schema.py:34-35, 41. |
| SCH-04 | Tracker Source + ATS Provider columns via tracker_utils.HEADERS | SATISFIED | scripts/schema.py:103-121 (TRACKER_COLUMNS); tracker_utils.py:46 imports as HEADERS. |
| SCH-05 | tests/test_migration.py round-trips fixture with 4 assertion classes | SATISFIED | tests/test_migration.py:56-105; 5 tests pass. |
| SCH-06 | file-contract.md lists runs.jsonl + daily/<DATE>/ats_raw/ | SATISFIED | file-contract.md lines 36, 52. |
| CON-01 | consolidate_targets.py KeyError on `already_applied` fixed | SATISFIED | consolidate_targets.py:274-276 documents the deletion; 0 grep matches for `already_applied`. |
| CON-02 | STATUS_VALUES enum + tracker append validation (warn-and-pass-through per locked decision) | SATISFIED | schema.py:55-90; tracker_utils.py:208-228; behavioral spot-check confirms 'dad' preserved + warned. |
| CON-03 | mine_connections.py WARNING + post-skip column validation | SATISFIED | mine_connections.py:49-58 (WARNING), 82-108 (column validation + ERROR abort). |
| CON-04 | All ImportError hints use pipx/venv | SATISFIED | 0 grep matches for `break-system-packages` across all 4 scripts. |
| CON-05 | LEGACY_DATA_DIRS removed; /scout-setup migration prompt | SATISFIED | state.py: 0 LEGACY_DATA_DIRS refs; scout-setup/SKILL.md:33-49 has the prompt. |
| CON-06 | Single canonical companies_per_day in templates/config.json | SATISFIED | templates/config.json:32 = 5; both skill docs use prose pointer; tightened regex returns 0 hits in skills/. |
| CON-07 | state.json 0o600 + ~/.job-scout 0o700 | SATISFIED | state.py:29-43 helper; lines 60-61, 75, 84 apply chmod. |

**Coverage:** 13/13 REQ-IDs technically covered in code; **SCH-02 has a runtime gap (plumbing exists, wiring missing).**

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| skills/scout-run/SKILL.md | (Step 4, after line 51) | Missing `ensure-today` invocation despite plumbing being in place | Warning | Phase 2 ATS writers will fail or silently mkdir on first write; the SC-4 contract is not met. |
| .planning/phases/01-schema-migration-paths-foundational-cleanup/01-01-schema-SUMMARY.md | line 16 | SUMMARY claims `normalize_application_status returns ("Active", True) on unknown values` — **factually wrong** vs. live source which returns `(s, True)` (the post-regression-fix behavior from commit e0863b2) | Info | SUMMARY documentation is stale relative to the post-fix code; not a code bug, just documentation drift. The live source IS correct (warn-and-pass-through preserves user data). |
| skills/scout-run/SKILL.md | (Step 4) | Computes `<TODAY>` (the local-date ISO string) but never persists it via `validate_data.py ensure-today` | Warning | Same root cause as the missing wiring above. |

### Human Verification Required

None for Phase 1 closure — all gaps are programmatically detectable.

### Gaps Summary

**One real gap (SC-4 partial):** `skills/scout-run/SKILL.md` does not invoke `validate_data.py ensure-today "<data_dir>" "<TODAY>"` after computing `<TODAY>`. The script-side support is complete (the function works, the CLI subcommand works, behavioral spot-check confirms it produces `daily/<DATE>/ats_raw/`), but no plan in Phase 1 was scoped to add the call site in the skill prompt.

This is a one-line fix in scout-run/SKILL.md (right after Step 4's "Compute today's run paths" block), and it is independent of Phase 2's ATS writer work — Phase 2 will assume the directory exists and write into it. If this gap is not closed in Phase 1, Phase 2 will either silently mkdir on first write (papering over the contract violation) or fail on first ATS payload write.

**One documentation drift (informational):** Plan 01-01 SUMMARY.md frontmatter at line 16 claims `normalize_application_status returns ("Active", True) on unknown values` but the live source (post commit e0863b2) returns `(s, True)` — the warn-and-pass-through behavior locked in CON-02. Not a code bug; the SUMMARY was written before the regression fix. Worth correcting for future-Claude reading the SUMMARY as authoritative.

**Recommendation:** Plan a single one-task closure plan that:
1. Adds the `ensure-today` invocation to skills/scout-run/SKILL.md Step 4.
2. (Optional) Updates Plan 01-01 SUMMARY.md frontmatter line 16 to reflect the post-fix `(s, True)` behavior.

---

_Verified: 2026-04-28T13:55:00Z_
_Verifier: Claude (gsd-verifier)_

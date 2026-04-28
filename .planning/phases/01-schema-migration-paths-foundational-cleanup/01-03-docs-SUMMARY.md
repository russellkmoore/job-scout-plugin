---
phase: 01-schema-migration-paths-foundational-cleanup
plan: 03
subsystem: docs
tags: [docs, skills, file-contract, ssot, legacy-migration, con-05, con-06, sch-06]
requirements: [SCH-06, CON-06]
key-files:
  created: []
  modified:
    - skills/job-scout/references/file-contract.md
    - skills/scout-run/SKILL.md
    - skills/job-scout/references/search-config.md
    - skills/scout-setup/SKILL.md
decisions:
  - "file-contract.md is the SSOT for paths. Two new rows added (runs.jsonl in Persistent files; daily/<DATE>/ats_raw/ in Per-run output) and both cross-reference the validators that create them (validate_runs_log + ensure_today_subdirs from Plan 01-01). Phase 2's runs.jsonl writer will reference this doc."
  - "Per CON-06 locked decision, templates/config.json is the SSOT for companies_per_day at value 5. Skill docs (scout-run/SKILL.md line 73; search-config.md line 43) now point at the template via prose ('see companies_per_day in templates/config.json') instead of quoting an inline numeric default. The verify regex was tightened per BLOCKER 5 to avoid false positives from future prose mentioning a digit elsewhere on the same line: companies_per_day[\"':$backtick][[:space:]]*[0-9]+ matches only config-style separator + digit, not prose with a digit further on."
  - "Legacy-dir migration prompt added to scout-setup/SKILL.md as the new Step 1 question 4 (renumbering the original 'Data directory' question 4 to 5). Detects three v0.3 legacy paths in order (~/Documents/JobSearch/scout, ~/Documents/JobSearch, ~/Documents/JobScout); for first match with config.json, prompts the user to reuse; on Yes, calls state.py write inline (locks the choice immediately so a mid-setup crash leaves a pointed dir; the existing Step 6 state.py write is still idempotent on top). This is the user-visible counterpart to Plan 01-02's LEGACY_DATA_DIRS deletion in scripts/state.py."
  - "Cross-reference scan ('Step 1 question 4' / Q4 anchors) returned zero matches across skills/. No stale references to update — clean ground."
  - "User's pre-existing uncommitted edits to skills/scout-run/SKILL.md (version bump to 0.3.3 + LinkedIn keyword-search section) were preserved across Task 2 by saving the file to /tmp, resetting to HEAD, applying only the Task 2 edit, committing, then restoring the user's edits on top of the new HEAD. Net result: 3 atomic commits each scoped to a single task; user's edits remain uncommitted at the same shape they were at session start."
metrics:
  duration_min: 4
  completed: 2026-04-28
  tasks: 3
  commits: 3
---

# Phase 1 Plan 3: Docs/skills schema sync Summary

## One-line summary

Aligned skill docs with v=4 paths and SSOT defaults: added `runs.jsonl` + `daily/<DATE>/ats_raw/` rows to `file-contract.md` (SCH-06), removed inline `companies_per_day` numeric defaults from two skill files in favor of pointing at `templates/config.json` (CON-06), and added a legacy-dir migration prompt to `scout-setup/SKILL.md` Step 1 so v0.3 users get a graceful upgrade path now that `LEGACY_DATA_DIRS` is gone (CON-05 user-facing).

## What was built

This plan finishes the user-facing/skill-doc work for Phase 1. Plans 01-01 + 01-02 (Wave 1) handled all `scripts/`-tier work; this Wave-2 plan reconciles the docs with the new code shape:

1. **Path SSOT extension (SCH-06)** — `skills/job-scout/references/file-contract.md` is the canonical path registry. v0.4 introduced two new artifacts (the run telemetry log + per-run ATS raw payloads); both now have rows in the appropriate tables and both cross-reference the validators that create them. Phase 2's runs.jsonl writer will look here, not at code.

2. **Default SSOT consolidation (CON-06)** — `templates/config.json` already had `companies_per_day: 5` (canonical). Two skill docs were drifting:
   - `skills/scout-run/SKILL.md:73` quoted "(default 8)" — stale from a prior config era.
   - `skills/job-scout/references/search-config.md:43` quoted "(default 8 in older configs, default 5 in template)" — even more stale, inconsistent on its face.

   Both now point at `templates/config.json` via prose ("see `companies_per_day` in `templates/config.json`"). The template stays at 5 (untouched). Future drift is impossible — there's exactly one place to edit.

3. **Legacy-dir migration prompt (CON-05 user-facing)** — Plan 01-02 deleted `LEGACY_DATA_DIRS` from `scripts/state.py`, which means existing v0.3 users without `~/.job-scout/state.json` now see "exit 2" on `/scout-run` startup with no auto-detection. This plan completes the user-visible half of CON-05: `skills/scout-setup/SKILL.md` Step 1 now detects the three known v0.3 paths in order, and for the first that exists with a `config.json`, prompts the user to reuse it. On Yes, the prompt calls `state.py write` **inline** (not deferred to Step 6) so the choice is locked before the rest of setup proceeds. On No (or no legacy detected), it falls through to the existing fresh-setup flow at the renumbered question 5.

## Files modified

| Path | Change | Commit |
|------|--------|--------|
| skills/job-scout/references/file-contract.md | +2 / −0 (runs.jsonl row + ats_raw/ row in the existing tables, cross-referencing validate_runs_log + ensure_today_subdirs) | 9c13181 |
| skills/scout-run/SKILL.md | +1 / −1 (line 73 inline default removed; replaced with prose pointing at templates/config.json) | 2e84994 |
| skills/job-scout/references/search-config.md | +1 / −1 (line 43 inline default removed; replaced with prose pointing at templates/config.json) | 2e84994 |
| skills/scout-setup/SKILL.md | +19 / −1 (new question 4 'Existing data directory check' inserted; original question 4 renumbered to 5) | 89971d4 |

Total: 4 files changed, +23 / −3.

## Tasks completed

- [x] Task 1 — Add runs.jsonl + daily/<DATE>/ats_raw/ entries to file-contract.md (SCH-06) — commit 9c13181
- [x] Task 2 — Remove inline companies_per_day defaults from skill docs; SSOT to templates/config.json (CON-06) — commit 2e84994
- [x] Task 3 — Add legacy-dir migration prompt to scout-setup/SKILL.md Step 1 (CON-05) — commit 89971d4

## Verify results

All three task-level verify blocks exited 0. The PLAN's plan-level verification block printed all three expected lines:

```
file-contract OK
companies_per_day SSOT OK
scout-setup legacy prompt OK
```

Per-task acceptance criteria (full pass):

- **Task 1:** `runs.jsonl`, `ats_raw/`, `validate_data.py:validate_runs_log`, `validate_data.py:ensure_today_subdirs`, `SCH-01`, `SCH-02` all present in file-contract.md. ✓
- **Task 2:** Tightened regex `companies_per_day["':$backtick][[:space:]]*[0-9]+` returns 0 matches across both verified files; both now grep-quote `templates/config.json`; templates/config.json untouched at value 5. ✓
- **Task 3:** "Existing data directory check", "~/Documents/JobSearch/scout", "~/Documents/JobScout", "scripts/state.py write", "CON-05" all present in scout-setup/SKILL.md; Step 1 numbered list now has 5 questions (1-5). The semantic intent of "standalone `~/Documents/JobSearch` distinct from `~/Documents/JobSearch/scout`" is satisfied — the file has both paths in distinct backtick-wrapped form on consecutive lines (36 and 37). ✓ See Deviation 1 below regarding the literal verify-regex shape.

## Deviations from Plan

**1. [Plan-authoring inconsistency — semantic-intent satisfied] Task 3 acceptance regex looked for double-quoted form**

- **Found during:** Task 3 verify.
- **Issue:** The plan's Task 3 acceptance criterion (and verify command) included `grep -q "~/Documents/JobSearch\""` — looking for the literal string `~/Documents/JobSearch"` (with a closing double-quote). Intent was clearly to confirm `~/Documents/JobSearch` exists distinctly from `~/Documents/JobSearch/scout` (i.e. the path closes with some non-`/` punctuation). However, the plan's prescribed `<action>` text uses backtick-wrapped markdown bullets (`` - `~/Documents/JobSearch` ``), not double-quoted strings — so the action and the verify regex are inconsistent on punctuation shape.
- **Fix:** Used the plan's prescribed action text verbatim (backticks). Confirmed the semantic intent with a different regex: `grep -E "~/Documents/JobSearch[^/]"` returns 1 match on line 37 (`` - `~/Documents/JobSearch` `` — distinct from line 36's `` `~/Documents/JobSearch/scout` ``). Did NOT add a redundant double-quoted form just to satisfy a literal regex that conflicts with the action.
- **Files modified:** None beyond the prescribed Task 3 edit.
- **Disposition:** Out-of-scope to fix the plan; semantic intent is satisfied. Logged here for audit.

**2. [Process — user's uncommitted edits preserved] Multi-step commit sequence on scout-run/SKILL.md**

- **Found during:** Task 2 staging.
- **Issue:** `skills/scout-run/SKILL.md` had user's pre-existing uncommitted edits at session start (version bump 0.3.1 → 0.3.3 + LinkedIn keyword-search section rewrite at lines 80-93). My Task 2 edit was at line 73 — a different line, no conflict. But staging the file with `git add` would have committed the user's edits along with mine.
- **Fix:** Saved the post-edit working-tree state of scout-run/SKILL.md to `/tmp/scout-run-SKILL-with-user-edits.md`, ran `git checkout HEAD -- skills/scout-run/SKILL.md` to restore the committed state, re-applied **only** the Task 2 single-line edit on the clean base, staged + committed, then restored the saved file from `/tmp` to put the user's uncommitted edits back on top of the new HEAD. Final `git status` shows the user's edits intact and uncommitted exactly as they were at session start.
- **Files modified:** No additional files beyond Task 2's prescribed edits.
- **Disposition:** Pre-flight prompt context flagged this exact situation and prescribed this protocol ("apply Plan 01-03 Task 2's edits ON TOP of that state … if a conflict is detected, do NOT silently overwrite"). No conflict was detected; user's edits preserved cleanly.

No Rule 1/2 auto-fixes. No Rule 4 architectural escalations. No CLAUDE.md-driven adjustments.

## Cross-reference scan results (Task 3 sub-step 0)

```
$ grep -rn 'Step 1[, ].*4\|[Qq]uestion 4\|[Qq]4' skills/
(no output)
```

Zero stale references found. The renumber 4→5 in scout-setup Step 1 has no documentation impact elsewhere in `skills/`. No additional updates needed.

## Threat model coverage

This plan implements the dispositions in PLAN's `<threat_model>`:

| Threat | Component | Implemented mitigation |
|--------|-----------|------------------------|
| T-03-01 (Tampering — config drift) | companies_per_day quoted in 3 places | Single SSOT in templates/config.json (value 5); skill docs reference the template via prose. Tightened regex avoids false-positive matches against unrelated digits. (CON-06) |
| T-03-02 (Information Disclosure — path documentation) | runs.jsonl + ats_raw/ paths potentially documented in two places | file-contract.md is the SSOT; both new rows cross-reference the creating validators. Phase 2 writer will reference here, not duplicate. (SCH-06) |
| T-03-03 (DoS — broken upgrade path) | v0.3 user runs /scout-run after Plan 01-02 deleted LEGACY_DATA_DIRS | scout-setup Step 1 detects the 3 legacy dirs, prompts reuse, calls state.py write inline (CON-05 user-facing). Cross-references audited (no stale 'question 4' anchors). |

## Deferred concerns (intentional)

- **Legacy-dir prompt UX iteration** — current prompt is a single AskUserQuestion per legacy match. If multiple legacy paths coexist on a system (rare), the prompt asks only about the first match and falls through to fresh setup if declined. Multi-match enumeration could be a v0.5 polish item but is over-engineered for the population of users this affects (probably < 5 v0.3 installations).
- **Self-validating SSOT links** — file-contract.md still relies on humans to keep the validator names current. A grep-based test that asserts the cross-referenced symbol names exist in `validate_data.py` would be defensible polish — Phase 1 Plan 04's grep gates partially cover this.
- **Verify-regex authoring consistency** — the Task 3 plan-authoring inconsistency (backticks in action vs. double-quotes in verify) is the kind of thing a plan-checker pass should catch; surfaced here for awareness, not in scope to fix.

## Self-Check

- [x] skills/job-scout/references/file-contract.md contains `runs.jsonl`, `ats_raw/`, `validate_data.py:validate_runs_log`, `validate_data.py:ensure_today_subdirs`, `SCH-01`, `SCH-02`
- [x] skills/scout-run/SKILL.md has the new prose `(see \`companies_per_day\` in \`templates/config.json\`)` on line 73; no `(default 8)` remains
- [x] skills/job-scout/references/search-config.md has the new prose `(see \`companies_per_day\` in \`templates/config.json\` for the canonical default)` on line 43; no `(default 8 in older configs...)` remains
- [x] templates/config.json untouched at `"companies_per_day": 5`
- [x] skills/scout-setup/SKILL.md Step 1 has 5 numbered questions (was 4); question 4 is "Existing data directory check (v0.4 CON-05)"; question 5 is "Data directory"; legacy paths all 3 listed; `state.py write` called inline; `CON-05` tag present
- [x] Cross-reference scan returned zero matches; no stale anchors needed updating
- [x] User's pre-existing uncommitted edits to `.claude-plugin/plugin.json` and `skills/scout-run/SKILL.md` preserved untouched (verified via `git status --short`)
- [x] All three task verify commands exited 0
- [x] Plan-level verification block printed all three expected lines
- [x] Commits 9c13181, 2e84994, 89971d4 all exist in git log
- [x] Each commit modified only the files scoped to its task; no out-of-scope drift

## Self-Check: PASSED

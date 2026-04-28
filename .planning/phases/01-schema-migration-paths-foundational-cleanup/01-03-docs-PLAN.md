---
phase: 01-schema-migration-paths-foundational-cleanup
plan: 03
type: execute
wave: 2
depends_on: [01-01-schema-PLAN, 01-02-cleanup-PLAN]
files_modified:
  - skills/job-scout/references/file-contract.md
  - skills/job-scout/references/search-config.md
  - skills/scout-run/SKILL.md
  - skills/scout-setup/SKILL.md
autonomous: true
requirements: [SCH-06, CON-06]

must_haves:
  truths:
    - "skills/job-scout/references/file-contract.md lists runs.jsonl AND daily/<DATE>/ats_raw/ as canonical paths in the existing tables"
    - "skills/scout-run/SKILL.md no longer quotes a numeric companies_per_day default — it points at templates/config.json"
    - "skills/job-scout/references/search-config.md no longer quotes a numeric companies_per_day default — it points at templates/config.json"
    - "skills/scout-setup/SKILL.md Step 1 detects the three legacy data dirs (~/Documents/JobSearch/scout, ~/Documents/JobSearch, ~/Documents/JobScout) and prompts the user to reuse one or set up fresh — calling state.py write to lock the choice"
    - "templates/config.json companies_per_day stays at 5 (the canonical default; do NOT modify)"
  artifacts:
    - path: skills/job-scout/references/file-contract.md
      provides: SSOT path registry with runs.jsonl + daily/<DATE>/ats_raw/ entries
    - path: skills/scout-run/SKILL.md
      provides: companies_per_day default reference points at config template (no inline number)
    - path: skills/job-scout/references/search-config.md
      provides: companies_per_day default reference points at config template (no inline number)
    - path: skills/scout-setup/SKILL.md
      provides: Step 1 includes a one-time legacy-dir migration prompt
  key_links:
    - from: skills/scout-run/SKILL.md
      to: templates/config.json
      via: "prose reference 'see companies_per_day in templates/config.json'"
      pattern: "templates/config\\.json"
    - from: skills/scout-setup/SKILL.md
      to: scripts/state.py write
      via: "Step 1 legacy-dir detection writes the chosen path via state.py write"
      pattern: "scripts/state\\.py write"
---

<objective>
Wave 2 documentation alignment. Three concerns:

- **SCH-06** — Add `runs.jsonl` and `daily/<DATE>/ats_raw/` as canonical entries in `skills/job-scout/references/file-contract.md`. file-contract.md is the path SSOT — Phase 2's runs.jsonl writer will reference it.
- **CON-05 (skill-side)** — Plan 02 deleted `LEGACY_DATA_DIRS` from `scripts/state.py`. Existing v0.3 users without state.json now see "exit 2" on `/scout-run` startup with no auto-detection of their data. Add a one-time legacy-dir migration prompt to `skills/scout-setup/SKILL.md` Step 1 that detects the three legacy paths, prompts the user to reuse one (writing it via `state.py write`) or set up fresh.
- **CON-06** — Single canonical `companies_per_day` default. `templates/config.json` is the SSOT (currently `5`). Remove the inline numeric default from `skills/scout-run/SKILL.md:73` and `skills/job-scout/references/search-config.md:43`; replace with prose pointing at the template.

Purpose: This plan runs in Wave 2 because (a) the file-contract update should reference the SAME `runs.jsonl` path that `validate_runs_log` (Plan 01) creates, and (b) the legacy-dir prompt in scout-setup is the user-visible counterpart to Plan 02's `LEGACY_DATA_DIRS` deletion. Wave-2 sequencing prevents documentation referring to code that doesn't exist yet.

Output: file-contract.md with two new path entries, scout-run/SKILL.md + search-config.md without numeric defaults, scout-setup/SKILL.md Step 1 with a legacy-dir migration prompt.

`templates/config.json` is NOT modified — it's already at the canonical value 5.
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
@skills/job-scout/references/file-contract.md
@skills/job-scout/references/search-config.md
@skills/scout-run/SKILL.md
@skills/scout-setup/SKILL.md
@templates/config.json

<interfaces>
<!-- Existing skill-doc structure the executor must respect. -->

From skills/job-scout/references/file-contract.md:
- "Persistent files in `{data_dir}`" table at lines 26-36 (file | path | owner triple)
- "Per-run output (always under `daily/`)" table at lines 41-50 (artifact | path)

From skills/scout-run/SKILL.md line 73:
"Pick `companies_per_day` companies (default 8) from `master_targets.csv`"
— the inline `(default 8)` quote is the drift site.

From skills/job-scout/references/search-config.md line 43:
"Take the top `config.search.companies_per_day` rows (default 8 in older configs, default 5 in template)."
— the inline `(default 8 in older configs, default 5 in template)` is the drift site.

From skills/scout-setup/SKILL.md Step 1 (lines 18-36):
Existing AskUserQuestion sequence: Resume path, LinkedIn export, Existing job tracking files, Data directory.
The legacy-dir migration prompt inserts BEFORE the "Data directory" question — so it can pre-populate the answer with a detected legacy path.

From scripts/state.py CLI (after Plan 02): `python3 scripts/state.py write <data_dir> [plugin_version]` writes state.json. The legacy-dir migration prompt calls this when the user accepts a detected dir.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add runs.jsonl + daily/&lt;DATE&gt;/ats_raw/ entries to file-contract.md</name>
  <files>skills/job-scout/references/file-contract.md</files>
  <read_first>
    - skills/job-scout/references/file-contract.md (the entire file — only 70 lines)
    - .planning/phases/01-schema-migration-paths-foundational-cleanup/01-RESEARCH.md (Open Questions item 6 — flat layout `daily/<DATE>/ats_raw/` not per-provider subdir notation)
  </read_first>
  <action>
    Make exactly these edits to `skills/job-scout/references/file-contract.md`:

    **Edit 1 — extend the "Persistent files in `{data_dir}`" table.** After the existing "Resume bank" row at line 35, add one new row:

    ```markdown
    | Run telemetry log | `{data_dir}/runs.jsonl` | `/scout-run` (appends one JSON line per run; created empty by `validate_data.py:validate_runs_log` at first run startup). v0.4 SCH-01. |
    ```

    **Edit 2 — extend the "Per-run output (always under `daily/`)" table.** After the existing "Per-A-tier packets (on demand)" row at line 50, add one new row:

    ```markdown
    | ATS raw payloads | `{data_dir}/daily/<DATE>/ats_raw/` (one file per provider response, created by `validate_data.py:ensure_today_subdirs` at run start). v0.4 SCH-02. |
    ```

    Per Open Question 6 in 01-RESEARCH.md, list the directory only — NOT a per-provider subdir layout. Phase 4 may extend with subdir notation if/when it's clear they're needed (vs flat `ats_raw/<company>__<provider>.json`).

    **Edit 3 — none for `templates/config.json`.** It's already canonical (companies_per_day=5). Do NOT touch.
  </action>
  <verify>
    <automated>cd /Users/rmoore/Workspaces/job-scout-plugin && grep -q "runs.jsonl" skills/job-scout/references/file-contract.md && grep -q "ats_raw/" skills/job-scout/references/file-contract.md && grep -q "validate_data.py:validate_runs_log" skills/job-scout/references/file-contract.md && grep -q "validate_data.py:ensure_today_subdirs" skills/job-scout/references/file-contract.md && echo OK</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "runs.jsonl" skills/job-scout/references/file-contract.md` returns 0
    - `grep -q "ats_raw/" skills/job-scout/references/file-contract.md` returns 0
    - `grep -q "SCH-01" skills/job-scout/references/file-contract.md` returns 0 (the v0.4 SCH-01 reference for traceability)
    - `grep -q "SCH-02" skills/job-scout/references/file-contract.md` returns 0
    - `grep -q "validate_runs_log" skills/job-scout/references/file-contract.md` returns 0 (cross-references the validator that creates the file)
    - `grep -q "ensure_today_subdirs" skills/job-scout/references/file-contract.md` returns 0
    - The verify command prints `OK`
  </acceptance_criteria>
  <done>
    `file-contract.md` lists `runs.jsonl` (under "Persistent files") and `daily/<DATE>/ats_raw/` (under "Per-run output"). Both rows cross-reference the validators that create them, satisfying the "every new path lives in exactly one place" rule.
  </done>
</task>

<task type="auto">
  <name>Task 2: Remove inline companies_per_day defaults from skill docs (CON-06)</name>
  <files>skills/scout-run/SKILL.md, skills/job-scout/references/search-config.md</files>
  <read_first>
    - skills/scout-run/SKILL.md (lines 70-90 — Step 2 Pass 1 description)
    - skills/job-scout/references/search-config.md (lines 35-55 — Pass 1 priority section)
    - templates/config.json (line 32 — confirms `companies_per_day: 5` is the canonical default)
  </read_first>
  <action>
    Per CON-06 locked decision: `templates/config.json` is the SSOT for `companies_per_day`. Remove inline numeric quotes from the two skill docs and replace with prose pointing at the template.

    **Edit 1 — `skills/scout-run/SKILL.md` line 73.** Find:
    ```markdown
    This is the highest-signal pass. Pick `companies_per_day` companies (default 8) from `master_targets.csv`:
    ```
    Replace the entire line with:
    ```markdown
    This is the highest-signal pass. Pick `companies_per_day` companies (see `companies_per_day` in `templates/config.json`) from `master_targets.csv`:
    ```

    **Edit 2 — `skills/job-scout/references/search-config.md` line 43.** Find:
    ```markdown
    3. Take the top `config.search.companies_per_day` rows (default 8 in older configs, default 5 in template).
    ```
    Replace the entire line with:
    ```markdown
    3. Take the top `config.search.companies_per_day` rows (see `companies_per_day` in `templates/config.json` for the canonical default).
    ```

    **Edit 3 — none for templates/config.json.** It's the SSOT — leave at 5.

    Self-check: after these edits, the only places quoting a numeric `companies_per_day` value across the repo should be `templates/config.json` (line 32, value 5) and `skills/scout-setup/SKILL.md` Step 5 (line 99 — `companies_per_day: 5, max_listings_per_run: 30`, which IS a description of the template defaults the setup populates and is internally consistent with the template — leave as-is). To prove the canonical-only rule:

    ```bash
    grep -nE "companies_per_day.*[0-9]" skills/scout-run/SKILL.md skills/job-scout/references/search-config.md
    ```

    must return zero matches after this task.
  </action>
  <verify>
    <automated>cd /Users/rmoore/Workspaces/job-scout-plugin && test "$(grep -cE 'companies_per_day.*[0-9]' skills/scout-run/SKILL.md skills/job-scout/references/search-config.md 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')" = "0" && grep -q "templates/config.json" skills/scout-run/SKILL.md && grep -q "templates/config.json" skills/job-scout/references/search-config.md && grep -q "\"companies_per_day\": 5" templates/config.json && echo OK</automated>
  </verify>
  <acceptance_criteria>
    - `grep -cE "companies_per_day.*[0-9]" skills/scout-run/SKILL.md` = `0` (no numeric default quoted)
    - `grep -cE "companies_per_day.*[0-9]" skills/job-scout/references/search-config.md` = `0`
    - `grep -q "templates/config.json" skills/scout-run/SKILL.md` returns 0 (the new prose reference)
    - `grep -q "templates/config.json" skills/job-scout/references/search-config.md` returns 0
    - `grep -q '"companies_per_day": 5' templates/config.json` returns 0 (template UNCHANGED, still 5)
    - The verify command prints `OK`
  </acceptance_criteria>
  <done>
    The two skill docs cite `templates/config.json` as the source of the `companies_per_day` default — no inline numbers. `templates/config.json` remains the SSOT at value 5.
  </done>
</task>

<task type="auto">
  <name>Task 3: Add legacy-dir migration prompt to scout-setup/SKILL.md Step 1</name>
  <files>skills/scout-setup/SKILL.md</files>
  <read_first>
    - skills/scout-setup/SKILL.md (lines 1-50 — Step 1 in full)
    - scripts/state.py (after Plan 02 lands — confirm `state.py write` CLI signature is unchanged)
    - .planning/phases/01-schema-migration-paths-foundational-cleanup/01-RESEARCH.md (Pattern 4 + the SKILL.md addition example at lines 805-820)
  </read_first>
  <action>
    Plan 02 deletes `LEGACY_DATA_DIRS` from `state.py`. Existing v0.3 users without state.json now see "exit 2" on /scout-run with no auto-detection. Add a one-time migration prompt to `/scout-setup` Step 1.

    **Edit — `skills/scout-setup/SKILL.md` Step 1.** The existing Step 1 starts at line 18 ("## Step 1: Welcome & data gathering") and uses `AskUserQuestion` to gather (1) Resume path, (2) LinkedIn export, (3) Existing job tracking files, (4) Data directory. Insert a new sub-step BEFORE the existing question 4 ("Data directory"). Find the line:

    ```markdown
    4. **Data directory** — "Where should I save everything?"
       - Default: `~/Documents/JobSearch/`
       - The directory must persist on the user's filesystem (i.e. NOT a session-scoped temp folder). If the user doesn't have a clear preference, accept the default.
       - Create the directory if missing: `mkdir -p <data_dir>` and `mkdir -p <data_dir>/daily` and `mkdir -p <data_dir>/assessment` and `mkdir -p <data_dir>/Resumes`.
    ```

    Replace it with:
    ```markdown
    4. **Existing data directory check (v0.4 CON-05)** — Before asking for a fresh data directory, check the three legacy locations from v0.3 in this exact order. For each that exists AND contains `config.json`, ask the user whether to reuse it:

       Legacy paths to check (in order):
       - `~/Documents/JobSearch/scout`
       - `~/Documents/JobSearch`
       - `~/Documents/JobScout`

       For the first one that exists with a `config.json`, use `AskUserQuestion`:
       > "Found an existing Job Scout data directory at `<path>`. Use this as your data_dir? (Yes / No, set up fresh)"

       If the user says **Yes**:
       - Set `<data_dir>` to that path.
       - Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state.py write "<data_dir>" "<plugin_version>"` to write the state pointer immediately (this is what locks the choice — without it, the next /scout-run won't find the dir, since `LEGACY_DATA_DIRS` was removed in v0.4).
       - Skip the "Data directory" question (5) below.
       - Continue with the rest of setup; existing config.json + master_targets.csv will be auto-migrated by `validate_data.py` on first /scout-run.

       If the user says **No** (or no legacy dir is detected), fall through to question 5.

    5. **Data directory** — "Where should I save everything?"
       - Default: `~/Documents/JobSearch/`
       - The directory must persist on the user's filesystem (i.e. NOT a session-scoped temp folder). If the user doesn't have a clear preference, accept the default.
       - Create the directory if missing: `mkdir -p <data_dir>` and `mkdir -p <data_dir>/daily` and `mkdir -p <data_dir>/assessment` and `mkdir -p <data_dir>/Resumes`.
    ```

    The renumber from 4→5 is intentional — keep the Step 1 question list contiguous.

    **Critical detail:** the `state.py write` call MUST happen inline in this step (not deferred to the existing Step 6 "Write the state pointer"). If the user accepts a legacy dir and we DON'T write state.json now, the rest of Step 1 (resume / LinkedIn / tracking files) proceeds without confirming the data_dir is locked — and a setup that crashes mid-flow leaves an unpointed legacy dir. The early `state.py write` makes the migration durable on the first crash-free moment.

    Step 6's existing `state.py write` at line 109 also still runs (it overwrites with the final plugin_version after setup completes). The two writes are idempotent.
  </action>
  <verify>
    <automated>cd /Users/rmoore/Workspaces/job-scout-plugin && grep -q "Existing data directory check" skills/scout-setup/SKILL.md && grep -q "~/Documents/JobSearch/scout" skills/scout-setup/SKILL.md && grep -q "~/Documents/JobSearch\"" skills/scout-setup/SKILL.md && grep -q "~/Documents/JobScout" skills/scout-setup/SKILL.md && grep -q "scripts/state.py write" skills/scout-setup/SKILL.md && grep -q "CON-05" skills/scout-setup/SKILL.md && echo OK</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "Existing data directory check" skills/scout-setup/SKILL.md` returns 0
    - `grep -q "~/Documents/JobSearch/scout" skills/scout-setup/SKILL.md` returns 0 (legacy path 1)
    - `grep -q "~/Documents/JobScout" skills/scout-setup/SKILL.md` returns 0 (legacy path 3 — distinct from `JobSearch`)
    - `grep -q "scripts/state.py write" skills/scout-setup/SKILL.md` returns 0 (the inline state-pointer write)
    - `grep -q "CON-05" skills/scout-setup/SKILL.md` returns 0 (traceability tag)
    - The Step 1 list is renumbered: question 4 is now "Existing data directory check," question 5 is "Data directory" — verify with `grep -c "^[0-9]\\." skills/scout-setup/SKILL.md` showing one MORE numbered question than before (4→5 in Step 1)
    - The verify command prints `OK`
  </acceptance_criteria>
  <done>
    `skills/scout-setup/SKILL.md` Step 1 detects existing v0.3 data dirs at the three known legacy paths, prompts the user to reuse one (calling `state.py write` inline to lock the choice), and falls through to a fresh setup if the user declines. Existing v0.3 users get a graceful upgrade path without re-running tooling against `LEGACY_DATA_DIRS` (which is gone after Plan 02).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| user → /scout-setup legacy-dir prompt | An adversarial user could decline the legacy-dir prompt and point at a different path; this is a feature, not a threat — the user gets to choose. |
| skill docs → executor | Stale prose in skill docs causes the LLM to over-fetch (companies_per_day inconsistency mid-run). Single SSOT in templates/config.json closes that drift. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-01 | Tampering (configuration drift) | companies_per_day quoted in 3 places | mitigate | Single SSOT in templates/config.json; skill docs reference the template (CON-06). Future drift is impossible — one source. |
| T-03-02 | Information Disclosure (path documentation) | runs.jsonl path + ats_raw/ path described in two places | mitigate | file-contract.md is the SSOT; Phase 2 writer references it. SCH-06 ensures the docstring rule "every new path lives in exactly one place" is honored. |
| T-03-03 | DoS (broken upgrade path) | v0.3 user runs /scout-run after Plan 02 deletes LEGACY_DATA_DIRS without re-running /scout-setup | mitigate | scout-setup Step 1 detects legacy dirs and prompts reuse, calling state.py write inline (CON-05 user-facing fix). The `/scout-run` exit-2 message tells the user to run /scout-setup. |
</threat_model>

<verification>
After all 3 tasks complete, run from repo root:

```bash
# 1. file-contract.md path entries
grep -q "runs.jsonl" skills/job-scout/references/file-contract.md
grep -q "ats_raw/" skills/job-scout/references/file-contract.md
echo "file-contract OK"

# 2. companies_per_day single-SSOT check
test "$(grep -cE 'companies_per_day.*[0-9]' skills/scout-run/SKILL.md skills/job-scout/references/search-config.md 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')" = "0"
grep -q '"companies_per_day": 5' templates/config.json
echo "companies_per_day SSOT OK"

# 3. legacy-dir migration prompt in scout-setup
grep -q "Existing data directory check" skills/scout-setup/SKILL.md
grep -q "scripts/state.py write" skills/scout-setup/SKILL.md
echo "scout-setup legacy prompt OK"
```

All three `OK` lines must print.
</verification>

<success_criteria>
- `file-contract.md` has new entries for `runs.jsonl` (Persistent files table) and `daily/<DATE>/ats_raw/` (Per-run output table) — both cross-referencing the validators that create them
- `skills/scout-run/SKILL.md` and `skills/job-scout/references/search-config.md` quote NO numeric `companies_per_day` default; both reference `templates/config.json`
- `templates/config.json` companies_per_day stays at 5 (the canonical SSOT)
- `skills/scout-setup/SKILL.md` Step 1 detects the 3 legacy data dirs and prompts the user to reuse or skip; reuse calls `state.py write` inline to lock the choice
- All three task verify blocks exit 0
</success_criteria>

<output>
After completion, create `.planning/phases/01-schema-migration-paths-foundational-cleanup/01-03-SUMMARY.md` summarizing the file-contract additions, the companies_per_day SSOT consolidation, and the scout-setup legacy-dir migration prompt.
</output>

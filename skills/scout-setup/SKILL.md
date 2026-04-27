---
name: scout-setup
description: Set up Job Scout — profile extraction from resume + LinkedIn export, honest career assessment, search config, and state pointer for daily runs. Triggers when the user types `/scout-setup` or asks to "set up the job scout", "configure job scout", "do first-time job scout setup".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, AskUserQuestion, TodoWrite
version: 0.3.1
---

Run the Job Scout first-time setup. This gathers the user's data, extracts their professional profile, generates an honest career assessment, writes a state pointer at `~/.job-scout/state.json`, and creates all configuration files needed for daily scout runs.

Read these before starting:
- `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/SKILL.md` (core skill knowledge)
- `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/file-contract.md` (where every file lives)
- `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/profile-extraction-guide.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/assessment-framework.md`

---

## Step 1: Welcome & data gathering

Use `AskUserQuestion` to gather these inputs. Ask them in sequence, not all at once:

1. **Resume path** — "Where is your resume? (PDF or DOCX file path)"
   - Use `Read` to verify it loads. PDFs are supported directly.

2. **LinkedIn data export** — "Do you have a LinkedIn data export? Request one at linkedin.com/mypreferences/d/download-my-data (takes ~24 hours)."
   - Yes → ask for the ZIP path.
   - No → proceed without it. Note that connection mining will be empty until the user re-runs setup with the export.

3. **Existing job tracking files** — "Do you have any existing job tracking files? (spreadsheets, CSVs with target companies)"
   - Yes → collect file paths.
   - No → start fresh.

4. **Data directory** — "Where should I save everything?"
   - Default: `~/Documents/JobSearch/`
   - The directory must persist on the user's filesystem (i.e. NOT a session-scoped temp folder). If the user doesn't have a clear preference, accept the default.
   - Create the directory if missing: `mkdir -p <data_dir>` and `mkdir -p <data_dir>/daily` and `mkdir -p <data_dir>/assessment` and `mkdir -p <data_dir>/Resumes`.

---

## Step 2: Questionnaire

Use `AskUserQuestion`. These fill gaps the resume doesn't answer:

1. Target salary minimum (total compensation, USD).
2. Open to relocation? Where? (Local only / US anywhere / US + International / custom)
3. Target role level. (Same / step up / open to lateral / custom)
4. Deal-breakers — industries, company sizes, arrangements they won't consider.
5. Roles they've actually gotten interviews for in the past year. *(Reveals true market positioning.)*
6. Roles they've been rejected from or gotten no response on. *(Reveals where the market says no.)*
7. Anything they know is a resume weakness.

---

## Step 3: Profile extraction

1. Analyze the resume per `references/profile-extraction-guide.md` and produce a structured `candidate_profile.json` matching the template at `${CLAUDE_PLUGIN_ROOT}/templates/candidate_profile.json`. Be honest about `strongest` vs `credible` vs `aspirational` skills.

2. If a LinkedIn export was provided:
   - Unzip and read `Skills.csv`, `Positions.csv`, `Profile.csv`. Cross-reference against the resume for inconsistencies.
   - Build the connections summary:
     ```bash
     python3 ${CLAUDE_PLUGIN_ROOT}/scripts/mine_connections.py \
       "<linkedin_export_path>/Connections.csv" \
       "<data_dir>/connections_summary.csv"
     ```

3. If the user provided existing tracking files, consolidate everything into `master_targets.csv`:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/consolidate_targets.py \
     --output "<data_dir>/master_targets.csv" \
     --connections "<data_dir>/connections_summary.csv" \
     --files <user_file_1> <user_file_2> ...
   ```
   The output schema is locked in `${CLAUDE_PLUGIN_ROOT}/scripts/schema.py` (`MASTER_TARGETS_COLUMNS`). Don't reference column names from anywhere else.

4. Save `candidate_profile.json` to `<data_dir>/candidate_profile.json`.

---

## Step 4: Honest assessment

Per `references/assessment-framework.md`:

1. Compare the extracted profile against the user's stated targets.
2. Identify sweet spots, stretches, underutilized assets, market challenges.
3. Write `<data_dir>/assessment/Honest_Career_Assessment.md`.
4. Summarize the **key honest take** in chat — do not just link the file. The user should hear the read.
5. Ask: "Does this resonate? Anything I'm wrong about?" Incorporate feedback into the profile if so.

---

## Step 5: Search strategy generation

1. Based on the profile + assessment, generate **6–8 primary search queries** plus 2–3 underutilized-asset queries tailored to this person's actual strengths. Don't reuse generic VP/Director templates blindly — let the assessment drive query phrasing.
2. Confirm the target company priority list (`master_targets.csv` is already populated; review the top 20 with the user, ask about any obvious omissions).
3. Configure scoring weights. Defaults from the template are reasonable; override only if the user has a strong preference. The defaults are:
   - connection_weight: 30, experience_match_weight: 25, domain_fit_weight: 20, compensation_weight: 15, realistic_shot_weight: 10
   - tier_a_threshold: 75, tier_b_threshold: 55
   - companies_per_day: 5, max_listings_per_run: 30
4. Write the complete `config.json` to `<data_dir>/config.json`. Use the template at `${CLAUDE_PLUGIN_ROOT}/templates/config.json` as the structural starting point and populate every field.

---

## Step 6: Write the state pointer

Lock in `data_dir` so `/scout-run` can find it deterministically:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state.py write "<data_dir>" "<plugin_version>"
```

Read `<plugin_version>` from `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`.

This writes `~/.job-scout/state.json`. From now on, the scout will not have to guess where the data lives.

---

## Step 7: Validate

Run the validator. It will create the empty tracker, ensure `daily/` exists, and confirm everything is wired up:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_data.py "<data_dir>"
```

If validation fails, surface the exact message, fix the issue, and re-run validation before declaring setup complete.

---

## Step 8: Confirmation

Present the setup summary:
- Profile summary (1 paragraph).
- Search queries that will run (primary + underutilized).
- Top 10 target companies by `linkedin_connection_count`.
- Scoring weights and tier thresholds.
- Pass budgets the daily run will use (defaults: 60% / 25% / 15%).
- Path to data directory + state pointer.

Ask: "Want to adjust anything before we finalize?" Apply edits, re-run `validate_data.py` if anything changed.

End with:
> Setup complete. Run `/scout-run` to search LinkedIn + career pages + other boards, or set up a scheduled task that just calls `/scout-run` (no overrides — the config in `<data_dir>/config.json` is the source of truth).

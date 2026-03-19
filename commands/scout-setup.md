---
description: Set up Job Scout — profile extraction, honest assessment, search config
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, AskUserQuestion, TodoWrite
---

Run the Job Scout first-time setup. This gathers the user's data, extracts their professional profile, generates an honest career assessment, and creates all configuration files needed for daily scout runs.

Read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/SKILL.md` to load the core job-scout skill knowledge.

## Step 1: Welcome & Data Gathering

Use AskUserQuestion to gather these inputs. Ask them in sequence, not all at once:

1. "Where is your resume? (PDF or DOCX file path)"
   - Read the resume using the Read tool once provided
   - If it's a PDF, use the Read tool directly (it handles PDFs)

2. "Do you have a LinkedIn data export? You can request one at linkedin.com/mypreferences/d/download-my-data — it takes about 24 hours."
   - Options: "Yes, I have it" / "Not yet, I'll get one"
   - If yes: ask for the file path (ZIP file)
   - If no: proceed without it, but note that connection mining will be incomplete

3. "Do you have any existing job tracking files? (spreadsheets, CSVs with target companies, etc.)"
   - Options: "Yes" / "No, starting fresh"
   - If yes: ask for file paths

4. "Where should I save everything?"
   - Default: ~/Documents/JobSearch/ (same folder as existing job search data if present)
   - Alternate: ~/Documents/JobScout/
   - Create the directory structure if it doesn't exist
   - **IMPORTANT:** Save to a folder the user has selected as their Cowork workspace, or files won't persist between sessions.

## Step 2: Questionnaire

Use AskUserQuestion for each question. These fill gaps the resume doesn't answer:

1. "What's your target salary? (minimum total compensation)"

2. "Are you open to relocation? If so, where?"
   - Options: "Local only" / "US anywhere" / "US + International" / custom

3. "What level of role are you targeting?"
   - Options: "Same level" / "Step up" / "Open to lateral moves" / custom

4. "Any deal-breakers? (industries, company sizes, arrangements you won't consider)"

5. "What roles have you actually gotten interviews for in the past year?"
   - This reveals true market positioning — what companies actually call back for

6. "What roles have you been rejected from or gotten no response?"
   - This reveals where the market says no

7. "Is there anything on your resume you know is a weakness?"
   - Candidates often know their gaps better than any analysis

## Step 3: Profile Extraction

Read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/profile-extraction-guide.md` for detailed instructions.

1. Analyze the resume — extract structured data per the candidate_profile.json schema
2. If LinkedIn export is available:
   - Unzip and read Skills.csv, Positions.csv, Profile.csv
   - Cross-reference against resume for gaps and inconsistencies
   - Run mine_connections.py to build company-level connection data:
     ```bash
     python3 ${CLAUDE_PLUGIN_ROOT}/scripts/mine_connections.py "<linkedin_export_path>/Connections.csv" "<data_dir>/connections_summary.csv"
     ```
3. If the user provided existing data files, run consolidate_targets.py:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/consolidate_targets.py --output "<data_dir>/master_targets.csv" --connections "<data_dir>/connections_summary.csv" --files <user_files>
   ```
4. Generate candidate_profile.json and save to the data directory
5. Copy the config.json template from `${CLAUDE_PLUGIN_ROOT}/templates/config.json` and populate it with the user's answers

## Step 4: Honest Assessment

Read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/assessment-framework.md` for the full framework.

1. Compare the extracted profile against the user's stated targets
2. Identify: sweet spots, stretches, underutilized assets, market challenges
3. Generate a full assessment report
4. Save to `<data_dir>/assessment/Honest_Career_Assessment.md`
5. Present the key findings to the user — do not just dump the file, summarize the honest take
6. Ask: "Does this resonate? Anything I'm wrong about?"
7. Incorporate feedback and update the profile if needed

## Step 5: Search Strategy Generation

1. Based on the profile analysis, generate 6-8 search queries tailored to THIS person's actual strengths
   - Each query targets a specific positioning angle
   - Include both primary (sweet spot) and secondary (stretch/underutilized) queries
2. Build the target company priority list from master_targets.csv
3. Configure scoring weights (use defaults unless user has strong preferences)
4. Write the complete config.json to the data directory

## Step 6: Confirmation

Present the setup summary:
- Profile summary (1 paragraph)
- Search queries that will run
- Top 10 target companies by connection count
- Scoring configuration
- Assessment style setting

Ask: "Want to adjust anything before we finalize?"

Save final config and tell the user: "Setup complete. Run /scout-run anytime to search LinkedIn, or set up a scheduled task for automatic daily runs."

# Phase 6: Run Summary + Delete Legacy + Milestone Close + Version/PII/Post-run Cleanup — Research

**Researched:** 2026-04-29
**Domain:** Close-out phase — no new infrastructure. Pure deletion, doc surgery, milestone verification helpers, and one new CLI subcommand in `runs_log.py`.
**Confidence:** HIGH

---

## Summary

Phase 6 is the milestone-close phase. No new Python packages. No new architectural patterns. All twelve requirements (OUT-01..07, CON-16..19, CON-21) fall into four categories:

1. **New code (two items):** A `milestone-bar` CLI subcommand added to `scripts/ats/runs_log.py` (OUT-07), and a post-write validation hook added to `/scout-run` Step 6 prose (CON-21).
2. **SKILL.md surgery (three items):** Step 2 old marketing-page Chrome pass-1 block deleted and rewritten as ATS-first (OUT-03/OUT-04); `[ATS-PREVIEW]` migration banners removed now that Phase 5 hoisted ATS into the main flow; run-summary block added to Step 6 and Step 9 (OUT-01/OUT-02).
3. **Doc/version cleanup (four items):** `plugin.json` + all SKILL.md frontmatter bumped lockstep to 0.4.0 (OUT-06/CON-16); `job-scout/SKILL.md:38` inline column list deleted (CON-17); PII note + `.gitignore` template added to `/scout-setup` (CON-18/CON-19); README updated (OUT-06).
4. **Grep gate (three items):** After the deletions, `grep -ri "career_page\|careers-html\|marketing-page" skills/ scripts/` and `grep -rn "\[ATS-PREVIEW\]" skills/ scripts/` must both return zero matches (OUT-03/OUT-04). `grep -h "^version:" skills/*/SKILL.md` must return exactly four `0.4.0` lines (CON-16).

The most complex item is the milestone bar measurement algorithm (OUT-07), which requires a new `milestone-bar` subcommand in `runs_log.py` and a clear definition of "Pass-1 share of A/B-tier candidates." That definition needs to be locked before planning — see Open Questions.

**Primary recommendation:** Plan this as five sequential plans: (1) Wave 0 tests for `milestone-bar` CLI; (2) `runs_log.py milestone-bar` subcommand; (3) SKILL.md surgery (delete legacy, remove `[ATS-PREVIEW]` banners, add run-summary block, add post-write validation hook); (4) doc/version/PII cleanup; (5) phase-wide grep gate + milestone bar verification.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Milestone bar computation | Python script (`runs_log.py`) | — | Reads `runs.jsonl` deterministically; no LLM needed |
| Run summary block in report | SKILL.md (LLM prose) | `runs_log.py milestone-bar` output | LLM formats; script provides the numbers |
| Run summary on stdout | SKILL.md (LLM prose) | Same script output | Mirror of report block |
| Legacy deletion verification | Grep gate (CI-style) | — | Binary yes/no; no ambiguity |
| Version bump | `plugin.json` + 4 SKILL.md frontmatter | — | String replacement; no logic |
| PII note | SKILL.md prose (`scout-setup/SKILL.md`) | — | User-facing warning in skill |
| Post-write validation | SKILL.md prose (`scout-run/SKILL.md`) | Optional Python check | LLM-enforced; can optionally call `validate_data.py` check |
| README | `README.md` | — | Markdown doc update |

---

## Standard Stack

Phase 6 adds zero new dependencies. All work uses existing infrastructure.

| Tool | Version | Purpose |
|------|---------|---------|
| `runs_log.py` | existing | Gets new `milestone-bar` subcommand for OUT-07 |
| `pytest` | 9.0.3 (installed) | Test the `milestone-bar` subcommand |
| `grep` | stdlib | Phase-wide deletion gate |
| `jq` | system | Human-readable milestone bar verification one-liner |

---

## Architecture Patterns

### Existing `runs_log.py` CLI Pattern

`runs_log.py` already has two CLI subcommands: `regression-suspects` and `pass2-board-broken`. Both follow the exact same shape. `milestone-bar` is a third subcommand using identical conventions. [VERIFIED: codebase read of `scripts/ats/runs_log.py`]

Pattern (from `_cmd_regression_suspects` / `_cmd_pass2_board_broken`):

```python
def _cmd_milestone_bar(args: List[str]) -> None:
    """milestone-bar <runs_log_path> [--lookback N]

    Reads the last N runs from runs.jsonl.
    Prints JSON with pass1_share_pct, wall_clock_avg_seconds, bar_met (bool).
    JSON is the LAST print per CONVENTIONS.md.
    """
    if not args:
        print("Usage: runs_log.py milestone-bar <runs_log_path> [--lookback N]", file=sys.stderr)
        sys.exit(1)

    runs_log_path = os.path.expanduser(args[0])
    lookback = 5
    if "--lookback" in args:
        lookback = int(args[args.index("--lookback") + 1])

    if not os.path.isfile(runs_log_path):
        print(json.dumps({"error": "runs.jsonl not found", "bar_met": False}))
        return

    with open(runs_log_path, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]

    result = compute_milestone_bar(lines, lookback=lookback)
    print(json.dumps(result, indent=2))
```

Add to `__main__` dispatch block:

```python
elif cmd == "milestone-bar":
    _cmd_milestone_bar(sys.argv[2:])
    sys.exit(0)
```

### Milestone Bar Computation Algorithm

**This is the most important algorithm in Phase 6.** The `compute_milestone_bar()` function computes two rolling averages over the last N runs from `runs.jsonl`.

**Pass-1 share definition (needs user confirmation — see Open Questions):**

Based on what `runs.jsonl` actually stores (verified from `runs_log.py` schema), each line has:
- `per_company_provider`: `{"{slug}|{provider}": {"outcome": "OK_WITH_RESULTS|OK_ZERO|ERROR", "listing_count": N}}`
- `providers`: per-provider summary counts

What `runs.jsonl` does NOT store per-run:
- A/B/C tier breakdown (that's in the daily report.md / tracker, not in runs.jsonl)
- LinkedIn listing counts vs ATS listing counts in final scored output

The ROADMAP defines Pass-1 share as "5-run rolling Pass-1 (ATS) share ≥ 60% of A/B-tier candidates." However `runs.jsonl` does not currently record A/B-tier tier-assignment results — it records raw dispatcher counts (how many listings were fetched from ATS, how many companies returned OK_WITH_RESULTS, etc.).

**Two viable interpretations:**

Option A — "ATS listing share of total listings fetched" (what runs.jsonl currently holds):
```
pass1_share = sum(listing_count for OK_WITH_RESULTS ATS outcomes) /
              total_listings_across_all_sources_this_run
```
Problem: `runs.jsonl` currently only records ATS Pass-1 fetched counts; it does not record Pass-2/Pass-3 listing counts in the same line. The `pass2_board_status` field records per-board zero/non-zero, not counts.

Option B — "ATS listing share of final A/B-tier scored listings" (requires writing A/B counts into runs.jsonl):
```
pass1_share = ats_ab_tier_count / (ats_ab_tier_count + linkedin_ab_tier_count)
```
This requires Phase 6 to also add `ab_tier_breakdown: {ats: N, linkedin: M}` to the runs.jsonl line written by preview.py / the end-of-run append. This is a new field, but it's the only way to make the milestone bar truly measure what the ROADMAP requires.

**Recommendation:** Option B is correct but requires extending the runs.jsonl schema. Phase 6 must add `ab_tier_counts` (or similar) to the runs.jsonl append in SKILL.md Step 7 / the stats.json passthrough. The `milestone-bar` subcommand reads this field. See Open Questions for user confirmation needed.

**Wall-clock average** is simpler — `wall_clock_seconds` is already in every runs.jsonl line:

```python
def compute_milestone_bar(
    lines: List[Dict[str, Any]],
    lookback: int = 5,
    pass1_share_target: float = 0.60,
    wall_clock_target_seconds: float = 300.0,  # 5 minutes
) -> Dict[str, Any]:
    """Compute 5-run rolling milestone bar metrics.

    Returns:
        {
          "lookback_used": N,        # actual runs available (min(lookback, len(lines)))
          "pass1_share_pct": 67.3,   # rolling avg ATS share % (or None if field absent)
          "wall_clock_avg_seconds": 187.4,
          "pass1_bar_met": True,     # >= 60%
          "wall_clock_bar_met": True, # <= 300s
          "bar_met": True,           # both True
          "runs_examined": [...]     # timestamps of the N runs used
        }
    """
    recent = lines[-lookback:] if len(lines) >= lookback else lines
    n = len(recent)
    if n == 0:
        return {"lookback_used": 0, "error": "no runs in file", "bar_met": False}

    wall_clocks = [r.get("wall_clock_seconds", 0) for r in recent]
    wall_clock_avg = sum(wall_clocks) / n

    # Pass-1 share: needs ab_tier_counts field (Phase 6 adds it).
    # Fall back to None if field absent (pre-Phase-6 runs).
    pass1_shares = []
    for r in recent:
        ab = r.get("ab_tier_counts")
        if ab:
            ats = ab.get("ats", 0)
            linkedin = ab.get("linkedin", 0)
            total = ats + linkedin
            if total > 0:
                pass1_shares.append(ats / total)
    pass1_share_avg = (sum(pass1_shares) / len(pass1_shares)) if pass1_shares else None

    pass1_bar_met = (pass1_share_avg is not None and pass1_share_avg >= pass1_share_target)
    wall_clock_bar_met = wall_clock_avg <= wall_clock_target_seconds

    return {
        "lookback_used": n,
        "pass1_share_pct": round(pass1_share_avg * 100, 1) if pass1_share_avg is not None else None,
        "wall_clock_avg_seconds": round(wall_clock_avg, 1),
        "pass1_bar_met": pass1_bar_met,
        "wall_clock_bar_met": wall_clock_bar_met,
        "bar_met": pass1_bar_met and wall_clock_bar_met,
        "runs_examined": [r.get("timestamp") for r in recent],
    }
```

The corresponding `jq` one-liner for manual verification (milestone bar criterion 5 from ROADMAP):

```bash
# Pass-1 share ≥ 60% AND wall-clock ≤ 5 min
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/runs_log.py milestone-bar \
  "<data_dir>/runs.jsonl" --lookback 5
```

### Run Summary Block Format (OUT-01/OUT-02)

The run-summary block goes at the **top** of `report.md` (before A-tier blocks) and mirrors to stdout at the end of the run. Based on ROADMAP success criteria SC-2, the block must contain:

```
## Run Summary — <TODAY>
- Total listings: <N>
- A-tier: <a> | B-tier: <b> | C-tier: <c>
- Pass-1 (ATS) share: <pct>% of A/B listings (<ats_ab> of <total_ab>)
- Wall-clock: <seconds>s
- Per-provider: greenhouse=<ok>ok/<zero>zero/<err>err  lever=...  (etc.)
- Top ATS regression suspects: <company/provider if any, else "none">
```

The summary block is composed at the end of Step 6 (report write) from:
1. The preview.py JSON summary (already available in SKILL from Step 2.5)
2. The A/B/C tier counts (computed during Step 5)
3. The `regression-suspects` output (already called in Step 6)

**stdout mirror:** Step 9 (Summarize to user) currently outputs a chat summary. The requirement (OUT-03) is that the summary block also appears on stdout at end-of-run. The simplest implementation: at the end of Step 7 (after tracker append), print the same summary block to stdout before the chat summary in Step 9. The key phrase from ROADMAP SC-2 is "visible in scheduled-run logs without opening the report file."

### Legacy Deletion Scope (OUT-03/OUT-04)

What counts as "marketing-page Chrome scraping" to delete:

**In `skills/scout-run/SKILL.md`:**

1. **Step 2 items 1 and 2** (lines 87-89): The "Career page (career_page_url) — read directly" and "ATS board" bullet points in the old Pass 1 Chrome loop. These describe Chrome-navigated scraping of marketing pages.
   - What to keep: item 3 (LinkedIn keyword scoped to company name) — this is legitimate LinkedIn pass-1 supplemental search, NOT marketing-page scraping.
   - What to delete: item 1 (career page direct navigation) and item 2 (ATS board via Chrome) from the Step 2 loop. Phase 5 replaced these with the ATS dispatcher (preview.py). Pass 1 via Chrome is now only the LinkedIn keyword search.
   - The Step 2 heading itself and the company-selection logic (sort/filter) stays.

2. **Step 2.5 `[ATS-PREVIEW]` migration banners**: The header "Phase 2 of the v0.4 ATS-first migration ships..." and "Phase 5 will replace the old flow; until then, both run." These are migration-phase scaffolding. Delete the migration prose, rename the section from "`[ATS-PREVIEW]` Pass 1" to "Pass 1 (ATS)" — the step itself is now the canonical path, not a preview.

3. **Step 2.5 report render sub-step**: The `[ATS-PREVIEW]` listing render block with "This is Phase 2-4 plumbing. Not scored, not tier-assigned. Phase 5 will hoist into Pass 1" — delete this. ATS listings are now fully scored and tier-assigned.

4. **`description:` frontmatter in scout-run/SKILL.md**: Currently says "broad sourcing across LinkedIn, career pages, and other boards." Update to "ATS-first sourcing (Greenhouse, Lever, Ashby, SmartRecruiters, Workday) + LinkedIn keyword search + specialized boards."

5. **Fallback Mode (bottom of SKILL.md)**: Currently says "Generate clickable URLs for every Pass 1 source (career page, ATS board, LinkedIn company jobs)." Update to remove "career page" (now ATS + LinkedIn only in fallback).

**In `skills/job-scout/references/chrome-setup.md`:**

Phase 5 already scoped this to LinkedIn-only (CON-11/CON-12 landed in Phase 5). The file currently ends with a "Performance Tips" section that mentions career page loading: "Career pages and ATS boards (Greenhouse, Lever, Workday, Ashby) generally return full JDs on first navigation — no scroll-and-expand dance required." This line is fine to keep (it's explanatory, not instructive) but the Fallback Mode section at the bottom referencing "company career pages" and "career page" should be checked and trimmed.

**Grep gates to verify (both must pass after deletion):**

```bash
# Gate 1: no marketing-page/career-page Chrome scraping prose
grep -ri "career_page\|careers-html\|marketing-page" skills/ scripts/ | grep -v ".pyc" | grep -v "career_page_url"
# Expected: zero matches (career_page_url column references are kept; "career page" as prose is deleted)

# Gate 2: no [ATS-PREVIEW] migration banners
grep -rn "\[ATS-PREVIEW\]" skills/ scripts/ | grep -v ".pyc"
# Expected: zero matches
```

Note: `career_page_url` as a column name reference must be preserved in `scripts/schema.py`, `scripts/consolidate_targets.py`, `skills/scout-run/SKILL.md` (JSON-LD routing uses it), and `skills/job-scout/SKILL.md`. The grep gate should be scoped to exclude the column name, hence `grep -v "career_page_url"` in the pipe.

The alternative cleaner gate from REQUIREMENTS.md:
```bash
grep -ri "career_page\|careers-html\|marketing-page" skills/ scripts/ | grep -v ".pyc"
```
This will still match `career_page_url` column references. The executor should decide whether to use the precise exclusion or accept that column-name references are not "scraping code."

### `[ATS-PREVIEW]` Banner Cleanup Scope

The `[ATS-PREVIEW]` tag appears in: [VERIFIED: grep]
- `skills/scout-run/SKILL.md` — 9 occurrences (migration prose, section header, report render block)
- `skills/scout-detect/SKILL.md` — 1 occurrence (Step 6 explanation: "Run [ATS-PREVIEW] Pass 1 against every row where ats_provider=greenhouse")
- `scripts/ats/preview.py` — docstring references (3 occurrences)

For `preview.py`: The docstring references are internal to the Python module — not user-visible in skills/ or scripts/ skill prose. They document the module's origin. These can stay as historical context or be updated to remove "Phase 2" references. Not strictly required for the OUT-04 grep gate since the gate is `grep -ri ... skills/ scripts/` but `[ATS-PREVIEW]` is not the same regex as `career_page|marketing-page`. The executor should decide whether to clean up `preview.py` docstrings or leave them.

For `scout-detect/SKILL.md:153`: The line "Run [ATS-PREVIEW] Pass 1 against every row where ats_provider=greenhouse" should be updated to say "Run ATS Pass 1 against every row where ats_provider is populated" (multi-provider, not just greenhouse, not [ATS-PREVIEW] branded).

### CON-16: Version Lockstep

Current version state: [VERIFIED: grep]
- `.claude-plugin/plugin.json`: `0.3.3`
- `skills/scout-run/SKILL.md`: `0.3.3`
- `skills/scout-setup/SKILL.md`: `0.3.1`
- `skills/job-scout/SKILL.md`: `0.3.0`
- `skills/scout-detect/SKILL.md`: `0.4.0` (already bumped in Phase 3)

All four SKILL.md files and `plugin.json` must read `0.4.0` after this phase.

Acceptance test:
```bash
grep -h "^version:" skills/*/SKILL.md
# Must return exactly 4 lines, all "version: 0.4.0"

python3 -c "import json; d=json.load(open('.claude-plugin/plugin.json')); assert d['version']=='0.4.0', d['version']"
# Must exit 0
```

### CON-17: Inline Column List Deletion

Current state in `skills/job-scout/SKILL.md` lines 38: [VERIFIED: codebase read]
```
- `MASTER_TARGETS_COLUMNS` — the master_targets.csv schema (v4). Includes `company_name`, `industry`, `career_page_url`, **`ats_provider`**, **`ats_board_url`**, `connection_names`, `linkedin_connection_count`, `application_status`, `fit_notes`, `last_checked`, `data_source`, `ats_slug_confidence`, `last_ats_hit_date`. Use `scripts/schema.py` as the authority; do not hardcode column names anywhere else.
```

The inline list (`Includes company_name, industry, career_page_url, ...`) is the problem — it both contradicts the instruction "do not hardcode column names" and is stale (it includes `career_page_url` but not `ats_slug_confidence` originally, and the `pipeline_tier` was removed).

Current state is partially correct: the v4 column names ARE accurate now (Phase 5 verified the schema). But the principle stands. Replace the `Includes ...` clause with:

```
- `MASTER_TARGETS_COLUMNS` — the master_targets.csv schema (v4). See `scripts/schema.py:MASTER_TARGETS_COLUMNS` for the canonical column list. Use `scripts/schema.py` as the authority; do not hardcode column names anywhere else.
```

Note: `skills/job-scout/SKILL.md` also has inline references to `career_page_url` in the body text at line 38 (within the column list). After CON-17 surgery, `career_page_url` still appears as a column reference — that's fine because it IS a valid schema column. The CON-17 goal is removing the inline `Includes` list, not suppressing all column name mentions.

### CON-18/CON-19: PII Handling Note + .gitignore Template

**Where in `/scout-setup`:** Add after Step 5 question 5 (data directory), before Step 6 (write state pointer), as a new "Important: data directory security" callout. This is where the user is choosing their `data_dir` and is most receptive to the guidance. [ASSUMED — could also go in Step 8 confirmation; either placement is defensible]

**PII note content (CON-18):**

```
**Important — PII and data directory security:**

Your `<data_dir>` contains sensitive data:
- `connections_summary.csv` and `master_targets.csv:connection_names` — LinkedIn connection data for potentially hundreds of third parties (names, companies, titles) who did not consent to be included.
- `candidate_profile.json` — your professional profile with salary targets and skill assessments.
- `config.json:candidate.resume_path` — absolute path to your resume.

**Do NOT place `<data_dir>` in:**
- iCloud Drive (syncs to Apple servers automatically)
- Dropbox / OneDrive / Google Drive (same risk)
- Any folder that auto-syncs to a shared device

Recommended: keep `<data_dir>` at `~/Documents/JobSearch/` (local-only on macOS by default unless you've enabled iCloud Desktop sync).
```

**`.gitignore` template entry + warning (CON-19):**

```
**If you ever share `config.json` (bug report, support thread, etc.):**
Always redact `candidate.resume_path` first — it exposes your filesystem layout.

A `.gitignore` template to prevent accidental git commits of your job search data:

\`\`\`
# Job Scout data directory — contains PII and personal data
<data_dir>/
*.csv
*.xlsx
config.json
candidate_profile.json
runs.jsonl
\`\`\`

Add this to the `.gitignore` of any project folder that's a parent of your `<data_dir>`.
```

### CON-21: Post-Write Validation at End of Step 6

The existing Step 6 writes `report.md`. The existing Step 7 appends to the tracker. The existing Step 9 does the chat summary.

**Where to add:** After Step 7 (tracker append), before Step 9 (chat summary). New content at the end of Step 7 (or as a new "Step 7.5" block):

```markdown
## Step 7.5: Post-write validation

After writing `report.md` (Step 6) and appending to the tracker (Step 7), verify that the run artifacts are consistent:

1. Confirm `<data_dir>/daily/<TODAY>/JobScout_Report_<TODAY>.md` exists and is non-empty.
2. Confirm `<data_dir>/runs.jsonl` has been appended this run (last line's `timestamp` contains `<TODAY>`).
3. Confirm that the A-tier count in the report (count the `### A-tier` entries) matches the A-tier row count appended to the tracker for `<TODAY>`.

If any check fails, print to stdout:
```
WARNING: post-run validation failed: <reason>
```

Where `<reason>` is one of:
- `report.md missing or empty`
- `runs.jsonl not appended today (last timestamp: <last_ts>)`
- `A-tier count mismatch: report has <N> but tracker has <M> for <TODAY>`

**Non-blocking:** A validation failure does NOT abort the run or delete anything. The warning is informational. It catches the "half-written report + fully-updated tracker" drift described in CONCERNS.md.

**Implementation note:** Step 7 already captures the tracker append stdout JSON (`new_rows.json` stats). The A-tier count is derivable from the new_rows.json array (filter for `tier == "A"`). Report existence is a simple `os.path.isfile` check. `runs.jsonl` recency is a `tail -1 | jq .timestamp` check.

Optionally, this check can be made deterministic via a new `validate_data.py post-run` subcommand, but SKILL.md prose checking is sufficient per the project's "LLM owns control flow" convention. No new Python module required.
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pass-1 share calc | Custom slice logic in SKILL.md prose | `runs_log.py milestone-bar` subcommand | Same pattern as `regression-suspects` and `pass2-board-broken` already in runs_log.py; keeps Pitfall-5-style arithmetic encapsulated |
| Version bump across 5 files | Manual multi-file edit | Simple sed/grep list; can delegate to cf-code-assistant | Risk is missing one file; enumerate explicitly |
| Grep gate logic | New Python test | Plain `grep -ri ... | wc -l` assertions | Binary pass/fail; existing pattern used in Phase 1 phase-wide gate |

---

## Common Pitfalls

### Pitfall 1: Grep gate catches `career_page_url` column references
**What goes wrong:** `grep -ri "career_page" skills/ scripts/` matches `career_page_url` everywhere it's used as a column name — schema.py, SKILL.md JSON-LD routing, consolidate_targets.py column alias map. The gate falsely fails.
**Why it happens:** The deletion target is "marketing-page Chrome scraping prose," not the column name.
**How to avoid:** Scope the grep to exclude the column name reference: `grep -ri "career_page\|marketing-page" skills/ scripts/ | grep -v ".pyc" | grep -v "career_page_url"`. Or use a whitelist approach: grep for the offensive prose patterns only (e.g., `"read directly"` near `career_page`, or `"navigate.*career"`).
**Warning signs:** Gate fails on schema.py or consolidate_targets.py.

### Pitfall 2: `[ATS-PREVIEW]` cleanup breaks preview.py docstring invariants
**What goes wrong:** Executor deletes all `[ATS-PREVIEW]` references including the `preview.py` module-level docstring, which describes the architectural contract (ONE process, ONE Client, ONE runs.jsonl append). Losing the docstring removes the DSP-03 rationale from the code.
**How to avoid:** Keep `preview.py` docstring intact (historical context is valuable). Only delete user-facing skill prose `[ATS-PREVIEW]` tags.

### Pitfall 3: Step 2 deletion removes the LinkedIn company-keyword pass
**What goes wrong:** The executor deletes all of Step 2 (items 1, 2, 3) instead of just items 1 and 2 (career-page Chrome navigation + ATS board Chrome navigation). Item 3 — the LinkedIn keyword search scoped to company name — is valid and must be preserved. It is NOT marketing-page scraping.
**How to avoid:** Surgical deletion: items 1 and 2 are deleted; item 3 stays. The "For each promising listing" extraction block that follows also stays.

### Pitfall 4: `ab_tier_counts` not wired into runs.jsonl
**What goes wrong:** `milestone-bar` subcommand is shipped but SKILL.md doesn't tell the LLM to write `ab_tier_counts` into the stats.json passthrough. The subcommand always returns `pass1_share_pct: null` because the field is never populated.
**How to avoid:** Phase 6 Plan 3 (SKILL.md surgery) MUST add a step in Step 7 / the stats.json construction that includes `"ab_tier_counts": {"ats": <count>, "linkedin": <count>}` derived from the scored candidate set. The `milestone-bar` subcommand test fixture must include a run with `ab_tier_counts` populated to prove the computation works end-to-end.

### Pitfall 5: Version bump misses `scout-detect/SKILL.md`
**What goes wrong:** `scout-detect/SKILL.md` is currently at `0.4.0` (already bumped in Phase 3). The other three are at 0.3.x. When the executor bumps all four, it might accidentally double-bump scout-detect or skip it.
**How to avoid:** Enumerate all four SKILL.md files explicitly. Verification command: `grep -h "^version:" skills/*/SKILL.md` must return exactly four `0.4.0` lines. Note: the glob `skills/*/SKILL.md` covers scout-run, scout-setup, job-scout, and scout-detect — all four.

### Pitfall 6: README version history omits 0.3.1 / 0.3.2 / 0.3.3 milestones
**What goes wrong:** README currently has 0.3.0 and 0.2.x sections. The 0.4.0 entry needs to summarize v0.4 capabilities without duplicating all phases. Adding a 0.4.0 bullet without acknowledging 0.3.x intermediate versions is fine — intermediate versions aren't shipped in the CHANGELOG; the README tracks milestone-level releases.

### Pitfall 7: Post-write validation uses fragile report line-count
**What goes wrong:** A-tier count comparison uses a line-count (`grep -c "^### "`) that matches all level-3 headers, not just A-tier. False positives if the report has other `###` sections (it does — "Honest notes", "Stale / skipped", etc.).
**How to avoid:** Count A-tier specifically: count lines matching `^### ` within the `### A-tier` section only, OR use the `new_rows.json` tier field (more reliable). The `new_rows.json` approach: `python3 -c "import json; rows=json.load(open('<path>/new_rows.json')); print(sum(1 for r in rows if r.get('tier')=='A'))"`.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OUT-01 | Every listing in `report.md` carries `source=` annotation | Phase 5 already wired `source=ats:<provider>` and `source=linkedin` in all listing blocks. Phase 6 confirms the format is present and adds it to the run-summary block. |
| OUT-02 | `report.md` opens with run-summary block (total listings, A/B/C counts, Pass-1 share %, wall-clock, per-provider breakdown, top 3 regression warnings) | New SKILL.md prose in Step 6 report header. Fields come from: preview.py JSON (ATS counts), scored candidate set (A/B/C), and `runs_log.py regression-suspects` output (already called in Step 6). |
| OUT-03 | `/scout-run` prints summary block to stdout at end of run | New SKILL.md prose in Step 9 or after Step 7. Mirror of OUT-02 block. |
| OUT-04 | All marketing-page Chrome scraping deleted from `skills/scout-run/SKILL.md` and `skills/job-scout/references/`; grep gate passes | Deletion surgery in Step 2 (items 1+2) and Step 2.5 migration banners. See "Legacy Deletion Scope" section. |
| OUT-05 | `chrome-setup.md` trimmed to LinkedIn-only; obsolete career-page sections removed | Phase 5 already handled CON-11/CON-12. Phase 6 removes any remaining "career page" references in the file. Currently the file is mostly LinkedIn-setup + troubleshooting. The one "career pages and ATS boards" explanatory line is borderline. |
| OUT-06 | `plugin.json` → 0.4.0; per-skill versions → 0.4.0; README updated | 5-file string replacement. README gets new v0.4 section summarizing ATS-first flow + `/scout-detect`. |
| OUT-07 | 5-run rolling Pass-1 share ≥ 60% verified; wall-clock ≤ 5 min verified | New `milestone-bar` subcommand in `runs_log.py` + `ab_tier_counts` field in runs.jsonl per-run. See algorithm section. |
| CON-16 | Version lockstep: plugin.json + all 4 SKILL.md frontmatter to 0.4.0 | Same as OUT-06 version bump. Grep gate: `grep -h "^version:" skills/*/SKILL.md` → 4 lines all `0.4.0`. |
| CON-17 | Delete inline column list in `skills/job-scout/SKILL.md:38` | 2-line edit: remove `Includes company_name, industry, ...` clause, replace with "see `scripts/schema.py:MASTER_TARGETS_COLUMNS`." |
| CON-18 | PII handling note + iCloud/Dropbox/OneDrive warning in `/scout-setup` Step 1 | New callout after data-directory question. Content specified in "CON-18/CON-19" section. |
| CON-19 | `.gitignore` template entry + "redact resume_path" warning in `/scout-setup` | Appended to CON-18 callout or as a separate Step 1 tail note. |
| CON-21 | Post-write validation at end of Step 6 (report exists, runs.jsonl appended today, A-tier count matches tracker) | New Step 7.5 block in `scout-run/SKILL.md`. Non-blocking WARNING if any check fails. |

---

## Validation Architecture

`nyquist_validation: true` in `.planning/config.json`. Include validation.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | none (rootdir autodiscovery) |
| Quick run command | `~/.job-scout-venv/bin/python3 -m pytest tests/test_runs_log_phase6.py -x -q` |
| Full suite command | `~/.job-scout-venv/bin/python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OUT-07 | `compute_milestone_bar` returns correct pass1_share from fixture with `ab_tier_counts` | unit | `pytest tests/test_runs_log_phase6.py::test_milestone_bar_pass1_share -x` | ❌ Wave 0 |
| OUT-07 | `compute_milestone_bar` wall-clock average across 5 runs | unit | `pytest tests/test_runs_log_phase6.py::test_milestone_bar_wall_clock -x` | ❌ Wave 0 |
| OUT-07 | `milestone-bar` CLI subcommand exits 0, prints JSON | unit | `pytest tests/test_runs_log_phase6.py::test_milestone_bar_cli -x` | ❌ Wave 0 |
| OUT-07 | `milestone-bar` with <5 runs uses available runs, not error | unit | `pytest tests/test_runs_log_phase6.py::test_milestone_bar_short_history -x` | ❌ Wave 0 |
| OUT-07 | `milestone-bar` with missing `ab_tier_counts` field returns `pass1_share_pct: null` | unit | `pytest tests/test_runs_log_phase6.py::test_milestone_bar_missing_field -x` | ❌ Wave 0 |
| CON-16 | `grep -h "^version:" skills/*/SKILL.md` returns exactly 4 `0.4.0` lines | grep gate | see phase-wide gate script | N/A (manual grep) |
| OUT-03/OUT-04 | `grep -ri career_page\|marketing-page skills/ scripts/` filtered by exclusions → 0 matches | grep gate | see phase-wide gate script | N/A (manual grep) |
| CON-21 | Post-write validation warning format (smoke — cannot fully unit test SKILL prose) | manual | review SKILL.md Step 7.5 prose after Phase 6 execution | N/A |

### Sampling Rate

- Per task commit: `~/.job-scout-venv/bin/python3 -m pytest tests/test_runs_log_phase6.py -x -q`
- Per wave merge: `~/.job-scout-venv/bin/python3 -m pytest tests/ -q`
- Phase gate: full suite green + phase-wide grep gate before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_runs_log_phase6.py` — 5 tests for `compute_milestone_bar` + CLI

No new conftest.py fixtures needed — the existing `conftest.py` and `tmp_path` pattern from Phase 5 tests is sufficient.

---

## Runtime State Inventory

> Omitting this section — Phase 6 is not a rename/refactor/migration phase. No string stored in external services, databases, or OS-registered state. The version bump is in git-tracked files only.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pytest | Wave 0 tests | ✓ | 9.0.3 (in ~/.job-scout-venv) | — |
| Python 3.x | All scripts | ✓ | 3.13.5 | — |
| jq | Manual milestone bar verification | ✓ (system) | system jq | Use `python3 -c "import json; ..."` |
| grep | Phase-wide gate | ✓ | system grep | — |

No missing dependencies.

---

## Milestone Bar Measurement Algorithm (Explicit)

This section is the primary research output for OUT-07. Lock this before planning.

### What runs.jsonl currently records per run

Each line has: [VERIFIED: codebase read of `runs_log.py`]
- `timestamp` (ISO 8601)
- `wall_clock_seconds` (float — the fetch_all duration from preview.py)
- `providers` (per-provider ok_with_results/ok_zero/error counts + field_completion)
- `per_company_provider` (per-(company, provider) outcome + listing_count)
- Optional: `dedup_decisions`, `regression_suspects`, `pass2_board_status`

### What is missing for milestone bar criterion 1

`runs.jsonl` currently does NOT record: total A+B tier listings by source (ATS vs LinkedIn). This is needed to compute "Pass-1 share of A/B-tier candidates."

### Required new field

Add `ab_tier_counts` to the runs.jsonl line written at end-of-run:

```json
"ab_tier_counts": {
  "ats": 4,
  "linkedin": 3,
  "total_ab": 7
}
```

This field is populated from the scored candidate set after Step 5 (enrich-then-tier). The SKILL.md stats.json passthrough (which already passes `dedup_decisions`, `regression_suspects`, `pass2_board_status` to `runs_log.append_run`) gets one more key: `ab_tier_counts`.

`runs_log.append_run` already accepts `**kwargs`-style Optional params. Add `ab_tier_counts: Optional[Dict[str, int]] = None` to the signature, same pattern as `dedup_decisions`.

### Milestone bar formula

```
pass1_share = ab_tier_counts["ats"] / ab_tier_counts["total_ab"]
5-run rolling average of pass1_share >= 0.60

wall_clock_avg = mean(wall_clock_seconds for last 5 runs)
wall_clock_avg <= 300.0
```

### jq one-liner (for human verification at milestone close)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/runs_log.py milestone-bar \
  "<data_dir>/runs.jsonl" --lookback 5
```

Expected output when milestone bar is met:
```json
{
  "lookback_used": 5,
  "pass1_share_pct": 67.3,
  "wall_clock_avg_seconds": 187.4,
  "pass1_bar_met": true,
  "wall_clock_bar_met": true,
  "bar_met": true,
  "runs_examined": ["2026-04-29T...", "2026-04-30T...", ...]
}
```

### Milestone bar criteria 3 and 4 (grep gates)

These are verified by grep gates, not by `runs.jsonl` computation:

**Criterion 3:** Zero marketing-page Chrome scraping references:
```bash
grep -ri "career_page\|careers-html\|marketing-page" skills/ scripts/ \
  | grep -v ".pyc" | grep -v "career_page_url"
# Expected: 0 lines
```

**Criterion 4:** Every listing carries `source=` tag — this is enforced by the report template in SKILL.md Step 6 (the `**Source:**` field in the A-tier block is required). Spot-check verification:
```bash
grep -c 'source=' <data_dir>/daily/<DATE>/JobScout_Report_<DATE>.md
# Expected: matches listing count
```

---

## Open Questions

1. **Pass-1 share definition — lock before planning**
   - What we know: ROADMAP says "Pass-1 (ATS) share ≥ 60% of A/B-tier candidates"; `runs.jsonl` does not currently record A/B tier counts by source.
   - What's unclear: Should Phase 6 add `ab_tier_counts` to `runs_log.append_run` (correct, but requires SKILL.md change to populate it), or should the milestone bar be defined as "ATS listings fetched / total listings fetched" (simpler, available from existing `per_company_provider`, but doesn't reflect final tier assignment)?
   - Recommendation: Add `ab_tier_counts` to `append_run` signature and SKILL.md stats.json passthrough. This is the defensible, correct measurement. Without it, the milestone bar could be "met" by fetching many ATS listings that all score C-tier, which is not the intent.
   - **User confirmation needed before planning.**

2. **Step 2 old Chrome pass — how much to delete vs rewrite**
   - What we know: Step 2 currently has three items: (1) career page navigation, (2) ATS board Chrome navigation, (3) LinkedIn keyword search. Items 1 and 2 are the old marketing-page scraping path. Item 3 is valid and stays.
   - What's unclear: Does Phase 6 delete items 1 and 2 entirely, or rewrite Step 2 to say "Pass 1 is now handled by Step 2.5 (ATS dispatcher); the remaining company-first activity is the LinkedIn keyword search in item 3"? The latter is more explicit about the v0.4 flow.
   - Recommendation: Rewrite Step 2 to make clear that ATS sourcing (preview.py) handles the ATS portion; Step 2 only orchestrates the LinkedIn keyword search for each company. Item 3 stays. Items 1 and 2 are deleted with a note: "ATS sourcing for this company's slate runs in Step 2.5 (all providers, one process)."
   - No user confirmation needed — this is within Claude's discretion.

3. **preview.py docstring cleanup**
   - What we know: `preview.py` has `[ATS-PREVIEW]` in its module docstring and several inline comments.
   - What's unclear: Is the OUT-04 grep gate intended to cover `scripts/` or just `skills/`? REQUIREMENTS.md OUT-04 says "from `skills/scout-run/SKILL.md` and `skills/job-scout/references/`" specifically. The ROADMAP SC-3 says "grep -ri ... skills/ scripts/" more broadly.
   - Recommendation: Clean up preview.py docstring to remove "Phase 2" and "[ATS-PREVIEW]" migration-banner language; keep the architectural explanation. This is low-risk and aligns with the broader grep gate.

4. **`source=` tag in all listing blocks — is it already complete?**
   - What we know: Phase 5 VERIFICATION confirms that all ATS listings carry `source=ats:<provider>` and LinkedIn listings carry `source=linkedin`. The report template in SKILL.md Step 6 has `**Source:**` as a required field.
   - What's unclear: Does OUT-01 require any new code, or is it a "verify and document" requirement? The tracker `source` column (SCH-04) was added in Phase 1.
   - Recommendation: OUT-01 is primarily a verification requirement + grep gate, not a code-change requirement. The planner should reflect this.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PII note goes after data-directory question in Step 1, before Step 6 | CON-18/19 section | Minor placement difference; either location is valid |
| A2 | `preview.py` docstring cleanup is within scope of OUT-04 grep gate | Legacy Deletion Scope | If out of scope, preview.py docstrings can stay; no functional impact |
| A3 | `wall_clock_seconds` in `runs.jsonl` already reflects the full /scout-run wall-clock (not just ATS fetch time) | Milestone Bar Algorithm | If wrong, OUT-07 would be measuring only ATS fetch time. May need SKILL to write a separate total_wall_clock field. Currently preview.py measures only `fetch_all` duration. |

**Note on A3:** This is a real risk. `preview.py`'s `wall_clock_seconds` is measured around `fetch_all()` only — the Python startup + file I/O overhead is excluded. The full /scout-run wall-clock (including Chrome navigation for enrichment, Pass 2, Pass 3) is NOT currently written to `runs.jsonl`. For the 5-minute milestone bar, "wall-clock" should mean the total run time, not just ATS fetch time. Phase 6 needs to decide: (a) add a `total_wall_clock_seconds` field to the final runs.jsonl append, OR (b) define "wall-clock" in the milestone bar as ATS-fetch-only (which is what's measurable today). Option (a) is correct but requires the SKILL to measure total run time and pass it to the final runs.jsonl append. This is a **user decision** if not already locked.

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | No | No new inputs |
| V6 Cryptography | No | No new crypto |
| CON-18 PII | Yes | Warning prose in skill — no encryption, just awareness |
| CON-19 Path disclosure | Yes | Warning prose — redact before sharing |

No new security surface area. CON-18/19 are documentation-level mitigations (awareness warnings), not technical controls.

---

## Sources

### Primary (HIGH confidence)
- Codebase read: `scripts/ats/runs_log.py` — verified existing CLI subcommand pattern and `append_run` signature
- Codebase read: `skills/scout-run/SKILL.md` — verified Step 2 scraping path, Step 2.5 `[ATS-PREVIEW]` blocks, Step 6 report format
- Codebase read: `skills/job-scout/SKILL.md` — verified CON-17 inline column list location
- Codebase read: `.planning/ROADMAP.md` Phase 6 section — verified all 12 requirements and success criteria
- Codebase read: `.planning/REQUIREMENTS.md` OUT-01..07, CON-16..19, CON-21 — verified exact requirement wording
- Codebase read: `.planning/phases/05-.../05-VERIFICATION.md` — verified Phase 5 delivered: extract_job_id deprecated, ATS-PREVIEW banner flagged for Phase 6 removal
- Live grep: version sprawl across 4 SKILL.md files + plugin.json confirmed
- Live grep: `[ATS-PREVIEW]` occurrences confirmed (skills/ + scripts/)
- Live grep: `career_page` / `marketing-page` occurrences confirmed

### Secondary (MEDIUM confidence)
- None — all research was from the codebase directly

### Tertiary (LOW confidence — not used)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps
- Architecture: HIGH — all patterns established in Phases 2–5
- Pitfalls: HIGH — derived from direct codebase inspection
- Milestone bar algorithm: MEDIUM — `ab_tier_counts` field is new; exact SKILL.md wiring needs user confirmation on measurement definition

**Research date:** 2026-04-29
**Valid until:** N/A — final phase; no external dependencies to expire

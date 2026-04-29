# Phase 6: Run Summary + Delete Legacy + Milestone Close + Version/PII/Post-run Cleanup — Pattern Map

**Mapped:** 2026-04-29
**Files analyzed:** 10 (new/modified)
**Analogs found:** 10 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scripts/ats/runs_log.py` (add `compute_milestone_bar` + `milestone-bar` subcommand) | utility | batch/transform | `runs_log.py` `_find_regression_suspects` / `_find_pass2_board_broken` + `_cmd_*` (same file) | exact |
| `scripts/ats/runs_log.py` (add `ab_tier_counts` param to `append_run`) | utility | CRUD | `runs_log.py` Phase 5 D-2 optional kwargs pattern (`dedup_decisions`, `regression_suspects`, `pass2_board_status`) | exact |
| `tests/test_runs_log_phase6.py` | test | batch | `tests/test_dedup_phase5.py` (synthetic JSONL via `tmp_path`, fixture file reads, `_find_*` function imports) | exact |
| `skills/scout-run/SKILL.md` (Step 2 surgery: delete items 1+2, rewrite Step 2.5 banners) | skill/config | request-response | `skills/scout-run/SKILL.md` Step 2 lines 78–108, Step 2.5 lines 149–223 (surgery targets are inline) | exact |
| `skills/scout-run/SKILL.md` (Step 5: add `ab_tier_counts` write to stats.json) | skill/config | CRUD | `skills/scout-run/SKILL.md` Step 7 `pass2_board_status` passthrough prose (lines 479–481) | exact |
| `skills/scout-run/SKILL.md` (Step 6: add run summary block; Step 9: stdout mirror; Step 7.5: post-write validation) | skill/config | request-response | `skills/scout-run/SKILL.md` Step 6 regression-suspects block (lines 439–459), Step 7 (lines 499–510) | role-match |
| `skills/scout-detect/SKILL.md` (reword `[ATS-PREVIEW]` reference at line 153; version bump) | skill/config | — | `skills/scout-detect/SKILL.md` frontmatter lines 1–6 | exact |
| `skills/scout-setup/SKILL.md` (version bump; add PII callout + `.gitignore` template after Step 1 Q5) | skill/config | — | `skills/scout-setup/SKILL.md` Step 1 lines 51–55 (data_dir question block, insertion point) | exact |
| `skills/job-scout/SKILL.md` (delete inline column list at line 38; replace with schema.py reference) | skill/config | — | `skills/job-scout/SKILL.md` line 38 (surgery target is inline) | exact |
| `.claude-plugin/plugin.json` (version bump 0.3.3 → 0.4.0) | config | — | `.claude-plugin/plugin.json` lines 1–8 | exact |
| `README.md` (v0.4 capabilities section) | doc | — | `README.md` lines 1–119 (current structure is the template) | role-match |

---

## Pattern Assignments

### `scripts/ats/runs_log.py` — `compute_milestone_bar` helper function

**Analog:** `runs_log.py` `_find_regression_suspects` (lines 168–224) and `_find_pass2_board_broken` (lines 227–264)

**Function signature pattern** (lines 168–172 and 227–233 as templates):
```python
def compute_milestone_bar(
    lines: List[Dict[str, Any]],
    lookback: int = 5,
    pass1_share_target: float = 0.60,
    wall_clock_target_seconds: float = 300.0,
) -> Dict[str, Any]:
```

**Slicing pattern** (Pitfall 5 — copy exactly from `_find_pass2_board_broken` lines 248–249):
```python
# _find_pass2_board_broken uses: recent = lines[-lookback:]
# compute_milestone_bar uses the SAME inclusive-of-current window:
recent = lines[-lookback:] if len(lines) >= lookback else lines
n = len(recent)
if n == 0:
    return {"lookback_used": 0, "error": "no runs in file", "bar_met": False}
```

**Optional field guard pattern** (lines 149–157 from `append_run` — same truthiness idiom):
```python
# For fields that may be absent on pre-Phase-6 runs (ab_tier_counts):
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
```

**Return dict pattern** (mirrors `_find_regression_suspects` return shape — flat dict, not list):
```python
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

---

### `scripts/ats/runs_log.py` — `_cmd_milestone_bar` CLI subcommand

**Analog:** `_cmd_regression_suspects` (lines 267–296) and `_cmd_pass2_board_broken` (lines 299–328)

**Command handler pattern** (copy structure from `_cmd_pass2_board_broken` lines 299–328):
```python
def _cmd_milestone_bar(args: List[str]) -> None:
    """milestone-bar <runs_log_path> [--lookback N]

    Reads runs.jsonl, calls compute_milestone_bar, prints JSON to stdout.
    JSON is the LAST print per CONVENTIONS.md (machine-consumable as final line).
    """
    if not args:
        print(
            "Usage: runs_log.py milestone-bar <runs_log_path> [--lookback N]",
            file=sys.stderr,
        )
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

**`__main__` dispatch addition** (copy from lines 365–370 pattern):
```python
elif cmd == "milestone-bar":
    _cmd_milestone_bar(sys.argv[2:])
    sys.exit(0)
```

**Usage help string addition** (copy from lines 339–340 pattern — add before the final `print(f"ERROR: Unknown command...")`):
```python
print("  milestone-bar <runs_log_path> [--lookback N]", file=sys.stderr)
```

---

### `scripts/ats/runs_log.py` — `ab_tier_counts` param in `append_run`

**Analog:** Phase 5 D-2 optional kwargs at `append_run` lines 98–100 and 149–157

**Signature extension** (add after `pass2_board_status` param, lines 100–101):
```python
    # Phase 6 D-1 addition — non-breaking; callers that don't pass it get None
    ab_tier_counts: Optional[Dict[str, int]] = None,
```

**Docstring addition** (mirrors Phase 5 D-2 docstring block at lines 124–128):
```
        ab_tier_counts: Phase 6 D-1 — {"ats": N, "linkedin": M, "total_ab": N+M}.
            Written after Step 5 enrich-then-tier in /scout-run.
            Used by milestone-bar subcommand to compute 5-run rolling Pass-1 share.
            Only emitted to line dict when non-None.
```

**Emit guard** (copy from `if pass2_board_status:` at line 156–157):
```python
    if ab_tier_counts:
        line["ab_tier_counts"] = ab_tier_counts
```

**`append-run` CLI dispatch** (add to stats passthrough at lines 351–363):
```python
        ab_tier_counts=stats.get("ab_tier_counts"),
```

---

### `tests/test_runs_log_phase6.py` — 5 unit tests

**Analog:** `tests/test_dedup_phase5.py` — entire file structure

**Module header pattern** (lines 1–24 of `test_dedup_phase5.py`):
```python
"""test_runs_log_phase6.py — Wave 0 RED tests for OUT-07 (milestone-bar subcommand).

Wave 0 commits these RED. Wave 1 (Plan 06-02 runs_log.py) turns them GREEN.

Run with:
    ~/.job-scout-venv/bin/python3 -m pytest tests/test_runs_log_phase6.py -x -q
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
```

**Synthetic JSONL via `tmp_path` pattern** (copy from `test_regression_suspects_logged` lines 325–349):
```python
def test_milestone_bar_cli(tmp_path):
    """OUT-07: milestone-bar CLI subcommand exits 0, prints JSON."""
    runs_log_path = tmp_path / "runs.jsonl"
    runs_log_path.write_text(
        json.dumps({
            "timestamp": "2026-04-29T10:00:00Z",
            "wall_clock_seconds": 200.0,
            "providers": {},
            "per_company_provider": {},
            "ab_tier_counts": {"ats": 4, "linkedin": 2, "total_ab": 6},
        }) + "\n"
    )
    # ... import and call _cmd_milestone_bar or subprocess runs_log.py
```

**Fixture-backed test pattern** (copy from `test_regression_suspect` lines 298–318):
```python
RUNS_JSONL_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "runs_jsonl_history.jsonl"

def test_milestone_bar_pass1_share():
    """OUT-07: compute_milestone_bar returns correct pass1_share from ab_tier_counts."""
    from ats.runs_log import compute_milestone_bar  # RED until Plan 06-02 lands
    # Build synthetic lines inline (no fixture needed for this unit test)
    lines = [
        {"timestamp": f"2026-04-2{i}T10:00:00Z",
         "wall_clock_seconds": 200.0,
         "ab_tier_counts": {"ats": 4, "linkedin": 2, "total_ab": 6}}
        for i in range(5)
    ]
    result = compute_milestone_bar(lines, lookback=5)
    assert result["pass1_share_pct"] == pytest.approx(66.7, abs=0.1)
    assert result["pass1_bar_met"] is True   # 66.7 >= 60
```

**Missing field / edge case pattern** (copy from `test_milestone_bar_missing_field` spec):
```python
def test_milestone_bar_missing_field():
    """OUT-07: absent ab_tier_counts returns pass1_share_pct: None (no crash)."""
    from ats.runs_log import compute_milestone_bar  # RED until Plan 06-02 lands
    lines = [{"timestamp": "2026-04-29T10:00:00Z", "wall_clock_seconds": 150.0}]
    result = compute_milestone_bar(lines, lookback=5)
    assert result["pass1_share_pct"] is None
    assert result["lookback_used"] == 1
```

---

### `skills/scout-run/SKILL.md` — Step 2 surgery (delete items 1+2, keep item 3)

**Surgery target** (lines 85–98 are the affected block):

Lines 87–89 are the DELETE targets:
```
1. **Career page** (`career_page_url`) — read directly. Career pages give full JDs...
2. **ATS board** (`ats_board_url`, if populated) — Greenhouse/Lever/Workday/Ashby...
   - If `ats_provider` is empty but `career_page_url` looks like `boards.greenhouse...
```

Line 90 onward (item 3, the LinkedIn keyword search) MUST BE PRESERVED verbatim.

**Replacement prose for Step 2 preamble** (rewrite lines 85–89 to this shape):
```markdown
For each selected company, ATS sourcing runs in Step 2.5 (all providers, one process).
The company-side activity in this step is the LinkedIn keyword search:

3. **LinkedIn jobs — keyword scoped to company name + candidate's location.**
```
(Item 3 content from line 90 onward stays unchanged.)

---

### `skills/scout-run/SKILL.md` — Step 2.5 banner surgery

**DELETE targets** (lines 149–215 contain the migration banners):

Line 149 heading: `## Step 2.5: [ATS-PREVIEW] Pass 1 (Greenhouse only) — additive`
Replace with: `## Step 2.5: Pass 1 (ATS) — all providers`

Line 151 block to DELETE (migration prose):
```
**What this is:** Phase 2 of the v0.4 ATS-first migration ships a structured ATS query
path... **Phase 5 will replace the old flow; until then, both run.** Do not interpret
the [ATS-PREVIEW] tag as scoring authority.
```
Replace with concise statement: `**What this is:** ATS-first sourcing using the multi-provider dispatcher. All providers run in one process.`

Line 193 subheading DELETE:
```
2. **Invoke the [ATS-PREVIEW] driver — ONE Bash call.**
```
Replace with: `2. **Invoke the ATS dispatcher — ONE Bash call.**`

Line 204 DELETE:
```
Capture stdout — the SKILL parses it to render the [ATS-PREVIEW] block in Step 6.
```
Replace with: `Capture stdout — the SKILL uses it to populate the run summary block in Step 6.`

Lines 206–215 (render block with `[ATS-PREVIEW]` label) DELETE and replace — see Step 6 run summary block pattern below.

---

### `skills/scout-run/SKILL.md` — Step 6 run summary block (new content)

**Analog:** Existing Step 6 `### ATS regression suspects` block (lines 439–459) — same "call a script, render output" pattern.

**New block to insert at top of Step 6 report** (after the `## Step 6: Build the daily report` heading, before `### Header`):

```markdown
### Run Summary block (top of report)

Insert the following block at the very top of `report.md`, before the A-tier sections:

\`\`\`
## Run Summary — <TODAY>
- Total listings: <N>
- A-tier: <a> | B-tier: <b> | C-tier: <c>
- Pass-1 (ATS) share: <pct>% of A/B listings (<ats_ab> of <total_ab>)
  - `pass1_share_pct` from: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/runs_log.py milestone-bar "<data_dir>/runs.jsonl" --lookback 1`
  - (single-run view; rolling average requires 5 runs)
- Wall-clock (ATS fetch): <wall_clock_seconds>s (from preview.py stdout `wall_clock_seconds` field)
- Per-provider: greenhouse=<ok>ok/<zero>zero/<err>err  lever=...  ashby=...  smartrecruiters=...  workday=...
- Top ATS regression suspects: <from regression-suspects output, or "none">
\`\`\`

Fields come from:
1. `preview.py` stdout JSON captured in Step 2.5 (`wall_clock_seconds`, `per_provider_outcomes`, `per_company_provider`)
2. Scored candidate set after Step 5 (`ab_tier_counts.ats`, `ab_tier_counts.linkedin`)
3. `regression-suspects` output already called at end of Step 6
```

**Step 5 `ab_tier_counts` write pattern** (mirrors Step 6 pass2_board_status passthrough prose at lines 479–481):
```markdown
After scoring all candidates, count A/B-tier listings by source and write to the
stats.json passthrough for the runs.jsonl append:

\`\`\`
"ab_tier_counts": {
  "ats": <count of A/B-tier listings where source starts with "ats:">,
  "linkedin": <count of A/B-tier listings where source == "linkedin">,
  "total_ab": <sum>
}
\`\`\`

This field is read by `runs_log.py milestone-bar` to compute the 5-run rolling Pass-1 share.
```

---

### `skills/scout-run/SKILL.md` — Step 9 stdout mirror (OUT-03)

**Analog:** Existing Step 9 (lines 525–533) — same chat-output structure.

**Addition after existing Step 9 chat summary** (new paragraph at line ~534):
```markdown
**Stdout summary (OUT-03):** After the chat summary, print the same Run Summary block
to stdout. This ensures the block is visible in scheduled-run logs without opening the
report file:

\`\`\`
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/runs_log.py milestone-bar \
  "<data_dir>/runs.jsonl" --lookback 1
\`\`\`

Print the JSON output followed by the human-readable run summary lines (same content as
the report header block above).
```

---

### `skills/scout-run/SKILL.md` — Step 7.5 post-write validation (CON-21)

**Analog:** `scripts/validate_data.py` `ensure-today` subcommand dispatch pattern (lines 154–162) — same "bash call + JSON result + non-zero exit on failure" shape.

**New Step 7.5 block to insert between Step 7 and Step 8**:
```markdown
## Step 7.5: Post-write validation (CON-21)

After writing `report.md` (Step 6) and appending to the tracker (Step 7), verify run
artifacts are consistent. Non-blocking — a failure prints a WARNING but does NOT abort:

1. **Report exists:** Confirm `<data_dir>/daily/<TODAY>/JobScout_Report_<TODAY>.md` exists
   and is non-empty.
   - Fail: `WARNING: post-run validation failed: report.md missing or empty`

2. **runs.jsonl appended today:** Confirm the last line of `<data_dir>/runs.jsonl` has a
   `timestamp` containing `<TODAY>`.
   ```bash
   python3 -c "
   import json; lines=open('<data_dir>/runs.jsonl').readlines()
   last=json.loads(lines[-1]) if lines else {}
   print(last.get('timestamp',''))
   "
   ```
   - Fail: `WARNING: post-run validation failed: runs.jsonl not appended today (last timestamp: <last_ts>)`

3. **A-tier count matches tracker:** Count A-tier rows from `<data_dir>/daily/<TODAY>/new_rows.json`:
   ```bash
   python3 -c "
   import json; rows=json.load(open('<data_dir>/daily/<TODAY>/new_rows.json'))
   print(sum(1 for r in rows if r.get('tier')=='A'))
   "
   ```
   Compare against A-tier blocks in `report.md` (count `### ` headings under `### A-tier` section
   only — NOT all level-3 headers to avoid Pitfall 7).
   - Fail: `WARNING: post-run validation failed: A-tier count mismatch: report has <N> but tracker has <M> for <TODAY>`
```

---

### `skills/scout-detect/SKILL.md` — line 153 reword + version bump

**Surgery target** (line 153):
```
- Run [ATS-PREVIEW] Pass 1 against every row where ats_provider="greenhouse" —
```

**Replacement** (reword to multi-provider, remove `[ATS-PREVIEW]` brand):
```
- Run ATS Pass 1 against every row where ats_provider is populated —
  producing real ATS listings tagged source=ats:<provider>
```

**Version bump target** (frontmatter line 5):
```
version: 0.4.0
```
Already at 0.4.0 — confirm it stays, do not re-edit.

---

### `skills/scout-setup/SKILL.md` — version bump + PII callout

**Frontmatter surgery target** (line 5):
```
version: 0.3.1
```
Replace with: `version: 0.4.0`

**PII callout insertion point:** After Step 1 Q5 (data directory question, line 55 — "Create the directory if missing..."), before the `---` separator at line 56. The insertion goes at the end of the Step 1 block.

**PII callout content pattern** (no existing analog — new prose block):
```markdown
> **Important — PII and data directory security:**
>
> Your `<data_dir>` contains sensitive data:
> - `connections_summary.csv` and `master_targets.csv:connection_names` — LinkedIn
>   connection data for potentially hundreds of third parties who did not consent.
> - `candidate_profile.json` — your professional profile with salary targets.
> - `config.json:candidate.resume_path` — absolute path to your resume.
>
> **Do NOT place `<data_dir>` in:**
> - iCloud Drive (syncs to Apple servers automatically)
> - Dropbox / OneDrive / Google Drive (same risk)
> - Any folder that auto-syncs to a shared device
>
> Recommended: `~/Documents/JobSearch/` is local-only on macOS by default unless
> iCloud Desktop sync is enabled.
>
> **If you ever share `config.json` (bug report, support thread, etc.):**
> Always redact `candidate.resume_path` first — it exposes your filesystem layout.
>
> A `.gitignore` template to prevent accidental git commits of your job search data:
>
> \`\`\`
> # Job Scout data directory — contains PII and personal data
> <data_dir>/
> *.csv
> *.xlsx
> config.json
> candidate_profile.json
> runs.jsonl
> \`\`\`
>
> Add this to the `.gitignore` of any project folder that is a parent of your `<data_dir>`.
```

---

### `skills/job-scout/SKILL.md` — CON-17 inline column list surgery

**Surgery target** (line 38 — exact current text):
```
- `MASTER_TARGETS_COLUMNS` — the master_targets.csv schema (v4). Includes `company_name`, `industry`, `career_page_url`, **`ats_provider`**, **`ats_board_url`**, `connection_names`, `linkedin_connection_count`, `application_status`, `fit_notes`, `last_checked`, `data_source`, `ats_slug_confidence`, `last_ats_hit_date`. Use `scripts/schema.py` as the authority; do not hardcode column names anywhere else.
```

**Replacement** (2-line edit — remove `Includes ...` clause):
```
- `MASTER_TARGETS_COLUMNS` — the master_targets.csv schema (v4). See `scripts/schema.py:MASTER_TARGETS_COLUMNS` for the canonical column list. Use `scripts/schema.py` as the authority; do not hardcode column names anywhere else.
```

**Note for planner:** `career_page_url` still appears in `job-scout/SKILL.md` body text as a column reference (e.g. JSON-LD routing prose). Those references are KEPT — CON-17 only removes the inline `Includes ...` enumeration, not all column name mentions.

---

### `.claude-plugin/plugin.json` — version bump

**Current state** (lines 1–8):
```json
{
  "name": "job-scout",
  "version": "0.3.3",
  "description": "Multi-source job search (career pages, ATS boards, ...) ...",
  "author": {
    "name": "Job Scout Contributors"
  }
}
```

**Target:** Change `"version": "0.3.3"` to `"version": "0.4.0"`.

**Description update** (optional but aligns with OUT-06): replace "career pages, ATS boards, ..." with "ATS-first sourcing (Greenhouse, Lever, Ashby, SmartRecruiters, Workday) + LinkedIn + specialized boards".

---

### `README.md` — v0.4 capabilities update

**Analog:** `README.md` lines 1–119 — full current structure

**Pass 1 description surgery** (lines 9–10 — current text):
```
1. **Pass 1 — Company-first deep-dive** (60% of effort). For each of your top target
   companies (sorted by warm connections × recency), it checks the company's own career
   page, detects the ATS provider (Greenhouse / Lever / Workday / Ashby), and falls back
   to LinkedIn's company jobs tab.
```
**Replacement:**
```
1. **Pass 1 — ATS-first sourcing** (60% of effort). For each of your top target
   companies, queries structured ATS APIs directly — Greenhouse, Lever, Ashby,
   SmartRecruiters, Workday — plus JSON-LD fallback for companies with no detected
   ATS. Then runs a LinkedIn keyword search scoped to each company name.
   Marketing-page Chrome scraping removed in v0.4.
```

**New v0.4 section to add** (insert before `## Requirements` at line 15):
```markdown
## What's new in v0.4

- **ATS-first sourcing.** Queries Greenhouse, Lever, Ashby, SmartRecruiters, and Workday
  APIs directly — no Chrome navigation of marketing pages.
- **JSON-LD fallback.** Companies with no ATS detected get a structured JSON-LD fetch
  on their career page URL.
- **`/scout-detect`.** Batch + inline detection of each company's ATS provider.
  Populates `ats_provider` + `ats_board_url` in `master_targets.csv`.
- **Cross-source dedup.** ATS and LinkedIn listings deduplicated with two-key fuzzy
  matching (rapidfuzz). Decisions logged to `runs.jsonl` for transparency.
- **Enrich-then-tier.** ATS A/B-tier candidates get LinkedIn shared-connection lookup
  before final tier assignment (restores warm-path signal).
- **Structured observability.** `runs.jsonl` records per-provider outcomes, field
  completion, dedup decisions, and A/B-tier counts per source. Regression suspects
  and board-broken warnings surface automatically.
- **Wall-clock target.** ATS fetch (Pass 1) runs concurrently with per-provider
  semaphore caps. `runs_log.py milestone-bar` reports the 5-run rolling ATS fetch
  average (target ≤ 5 min). Note: "wall-clock" here is ATS-fetch only, not total
  `/scout-run` wall-clock.
```

**Requirements section update** (line 22 — `pip install` guidance):
```
- Python 3.8+ with `pandas`, `openpyxl`, `httpx>=0.27,<0.29`, `rapidfuzz`
  (`pipx install` or `python3 -m venv` recommended; see install hints on first run)
```

---

## Shared Patterns

### Version bump lockstep
**Source:** `.claude-plugin/plugin.json` (current: `0.3.3`), `skills/scout-run/SKILL.md` line 5 (`0.3.3`), `skills/scout-setup/SKILL.md` line 5 (`0.3.1`), `skills/job-scout/SKILL.md` line 5 (check — currently at 0.3.0)
**Apply to:** All four files, all to `0.4.0` in one plan
**Acceptance gate:**
```bash
grep -h "^version:" skills/*/SKILL.md
# Must return exactly 4 lines, all: version: 0.4.0
python3 -c "import json; d=json.load(open('.claude-plugin/plugin.json')); assert d['version']=='0.4.0'"
```
**Critical:** `scout-detect/SKILL.md` is ALREADY at `0.4.0` (confirmed line 5). Do not double-bump. Only 3 SKILL.md files need editing: scout-run, scout-setup, job-scout.

### `sys.argv[1]` subcommand dispatch
**Source:** `scripts/validate_data.py` lines 147–162 and `scripts/ats/runs_log.py` lines 331–372
**Apply to:** `runs_log.py` `__main__` dispatch (adding `milestone-bar` branch)
```python
# Pattern from runs_log.py lines 365–370:
elif cmd == "regression-suspects":
    _cmd_regression_suspects(sys.argv[2:])
    sys.exit(0)
elif cmd == "pass2-board-broken":
    _cmd_pass2_board_broken(sys.argv[2:])
    sys.exit(0)
# Add after pass2-board-broken:
elif cmd == "milestone-bar":
    _cmd_milestone_bar(sys.argv[2:])
    sys.exit(0)
```

### Optional kwargs pattern for `append_run`
**Source:** `runs_log.py` lines 98–101 and 149–157
**Apply to:** `ab_tier_counts` parameter addition
```python
# Existing Phase 5 pattern at lines 98–101:
dedup_decisions: Optional[List[Dict[str, Any]]] = None,
regression_suspects: Optional[List[Dict[str, Any]]] = None,
pass2_board_status: Optional[Dict[str, int]] = None,
# New Phase 6 param follows the same shape:
ab_tier_counts: Optional[Dict[str, int]] = None,

# Existing emit guard pattern at lines 149–157:
if dedup_decisions:
    line["dedup_decisions"] = dedup_decisions
# New emit guard:
if ab_tier_counts:
    line["ab_tier_counts"] = ab_tier_counts
```

### Grep gate verification pattern
**Source:** Phase-wide gate in `06-VALIDATION.md`
**Apply to:** Plan 06-N (final verification plan)
```bash
# Grep Gate 1: marketing-page Chrome scraping deleted
grep -rni "marketing-page\|marketing page" skills/ scripts/ --exclude-dir=__pycache__ | wc -l
# Must equal 0

# Grep Gate 2: [ATS-PREVIEW] banners deleted
grep -rn "\[ATS-PREVIEW\]" skills/ scripts/ --exclude-dir=__pycache__ | wc -l
# Must equal 0

# Grep Gate 3: career_page prose deleted (column references allowed)
grep -ri "career_page\|careers-html" skills/ scripts/ | grep -v ".pyc" | grep -v "career_page_url"
# Must equal 0

# Grep Gate 4: inline column list deleted
grep -c "company_name.*linkedin_connection_count.*ats_provider" skills/job-scout/SKILL.md
# Must equal 0

# Grep Gate 5: version lockstep
grep -h "^version:" skills/*/SKILL.md | grep -c "0.4.0"
# Must equal 4 (all 4 SKILL.md files including scout-detect which was already 0.4.0)
```

---

## No Analog Found

All Phase 6 files have direct analogs. No "no analog" entries.

| File | Closest analog chosen | Why no exact match |
|---|---|---|
| PII callout prose in `scout-setup/SKILL.md` | Existing Step 1 data-dir Q5 block (lines 51–55) | No prior PII warning pattern in the codebase — content is new prose, placement is clear |
| README v0.4 section | README.md lines 1–119 (current structure) | Existing README structure is the template; the section itself is new content |

---

## Critical Pitfall Reminders (for planner action items)

1. **Pitfall 1 — Grep gate false positives on `career_page_url`:** Use `grep -v "career_page_url"` exclusion on the grep gate, OR confirm that `career_page_url` column references are explicitly out-of-scope for the deletion gate. Do NOT remove `career_page_url` from `schema.py`, `consolidate_targets.py`, or SKILL.md JSON-LD routing.

2. **Pitfall 3 — Step 2 over-deletion:** Delete items 1 and 2 ONLY (lines 87–89). Item 3 (LinkedIn keyword search, line 90 onward) is preserved. The Step 2 heading and sort/filter logic (lines 80–84) stay.

3. **Pitfall 4 — `ab_tier_counts` wiring:** `milestone-bar` is useless if SKILL.md never writes `ab_tier_counts` to the stats.json passthrough. Plan 06-03 (SKILL.md surgery) must include the Step 5 write instruction — it is load-bearing for OUT-07.

4. **Pitfall 5 — Version bump counts:** scout-detect is already `0.4.0`. Only 3 SKILL.md files need bumping. Acceptance grep returns 4 lines (all 4 SKILL.md files), not 3.

5. **Pitfall 7 — A-tier count in Step 7.5:** Use `new_rows.json` tier field, not `grep -c "^### "` (which matches all level-3 headers). The `python3 -c "... sum(1 for r in rows if r.get('tier')=='A')"` pattern is the correct one.

---

## Metadata

**Analog search scope:** `scripts/ats/`, `tests/`, `skills/*/SKILL.md`, `skills/job-scout/references/`, `.claude-plugin/`, `README.md`
**Files scanned:** 11 (runs_log.py, test_dedup_phase5.py, scout-run/SKILL.md, scout-detect/SKILL.md, scout-setup/SKILL.md, job-scout/SKILL.md, validate_data.py, plugin.json, README.md, 06-RESEARCH.md, 06-VALIDATION.md)
**Pattern extraction date:** 2026-04-29

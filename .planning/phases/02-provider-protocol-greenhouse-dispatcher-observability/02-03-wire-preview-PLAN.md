---
phase: 02-provider-protocol-greenhouse-dispatcher-observability
plan: 03
type: execute
wave: 3
depends_on: [02-01-dispatcher-PLAN, 02-02-greenhouse-PLAN]
files_modified:
  - scripts/ats/preview.py
  - skills/scout-run/SKILL.md
autonomous: true
requirements: [DSP-10]

must_haves:
  truths:
    - "scripts/ats/preview.py exists as a thin driver script: takes (data_dir, today, slugs_csv); calls dispatcher.fetch_all() ONCE (single httpx.Client lifetime via fetch_all's `with httpx.Client(...) as client:` block); persists raw payloads from the returned outcomes to <data_dir>/daily/<TODAY>/ats_raw/<provider>/<company>.json; appends ONE runs.jsonl line via runs_log.append_run; prints the per-(company, provider) summary as JSON to stdout for the SKILL prompt."
    - "skills/scout-run/SKILL.md gains a new Step 2.5 [ATS-PREVIEW] block placed AFTER Step 2 (the company-first deep-dive) and BEFORE Step 3 (Pass 2 — other boards). Existing Step 1/2/3/4/5/6/7/8/9 + Fallback Mode flow remains intact and still produces output (additive, non-breaking — DSP-10 locked decision)."
    - "The [ATS-PREVIEW] block calls scripts/ats/preview.py EXACTLY ONCE per /scout-run with a single CLI invocation — NOT three. ONE process invocation → ONE fetch_all → ONE httpx.Client lifecycle → ONE wall_clock measurement → ONE runs.jsonl append → raw[] and stats from the SAME outcomes (DSP-03 contract preserved at the SKILL boundary)."
    - "The block writes one runs.jsonl line per /scout-run via runs_log.append_run() (DSP-07 wiring). The append happens inside preview.py at the end of the single fetch_all call."
    - "The user's pre-existing uncommitted edits to skills/scout-run/SKILL.md (frontmatter version 0.3.3 + Step 2 LinkedIn URL pattern with f_C-disabled rationale) are PRESERVED VERBATIM via the stash-replay protocol Plan 01-03 used. Final git status shows the edit applied + the user's pending edits restored on top, both still uncommitted."
    - "Phase 2 does NOT touch scoring or tier assignment. The [ATS-PREVIEW] tag is the only signal — Phase 5 hoists ATS into Pass 1 anchor + applies the +1 tier bump."
  artifacts:
    - path: scripts/ats/preview.py
      provides: Single-fetch_all driver — ONE process per /scout-run; persists raw + appends runs.jsonl + emits stdout summary.
      exports: ["run_preview"]
      min_lines: 60
    - path: skills/scout-run/SKILL.md
      provides: New Step 2.5 [ATS-PREVIEW] section between current Step 2 and Step 3 — single CLI invocation of preview.py
      contains: 'ATS-PREVIEW'
  key_links:
    - from: scripts/ats/preview.py
      to: scripts/ats/dispatcher.py
      via: "from ats.dispatcher import fetch_all, aggregate_outcomes"
      pattern: "from ats.dispatcher import"
    - from: scripts/ats/preview.py
      to: scripts/ats/runs_log.py
      via: "from ats.runs_log import append_run"
      pattern: "from ats.runs_log import"
    - from: skills/scout-run/SKILL.md
      to: scripts/ats/preview.py
      via: "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/preview.py <data_dir> <TODAY> <slugs_csv>"
      pattern: "scripts/ats/preview.py"
    - from: scripts/ats/preview.py
      to: <data_dir>/daily/<TODAY>/ats_raw/
      via: "writes <provider>/<company>.json under ats_raw/"
      pattern: "ats_raw"
---

<objective>
Wire Phase 2's substrate (Plans 02-01 + 02-02) additively into `/scout-run` as a NEW Step 2.5 ([ATS-PREVIEW] hook) — alongside the existing 3-pass flow, without changing scoring or tier assignment.

Per DSP-10 locked decision: "old flow still produces output; new ATS pass writes raw responses to daily/<DATE>/ats_raw/<provider>/<company>.json and is visible in the report behind a [ATS-PREVIEW] tag (so Phase 2 doesn't change scoring or tier assignment yet). Phase 5 will replace the old flow."

**Architectural anchor: a single fetch_all per /scout-run.** The DSP-03 contract says ONE shared httpx.Client per run. To honor that at the SKILL boundary (where multiple Bash invocations would otherwise instantiate multiple clients), all three responsibilities — invoke the dispatcher, persist raw payloads, append runs.jsonl — are collapsed into a single thin driver script (`scripts/ats/preview.py`) that the SKILL invokes exactly once. The SKILL is one CLI call; preview.py owns the single fetch_all lifetime.

This plan touches exactly TWO files — `scripts/ats/preview.py` (new) and `skills/scout-run/SKILL.md` (additive Step 2.5) — and the user has 2 pending uncommitted hunks in scout-run/SKILL.md. The stash-replay protocol from Plan 01-03 preserves the user's pending edits while we land Plan 02-03's edit on top.

Output:
1. `scripts/ats/preview.py` — thin driver, one fetch_all call, persists raw + appends runs.jsonl + prints summary JSON.
2. New `## Step 2.5: [ATS-PREVIEW]` block in scout-run/SKILL.md invoking preview.py once.

The existing flow (Steps 0-9 + Fallback Mode) continues unchanged.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/02-provider-protocol-greenhouse-dispatcher-observability/02-01-dispatcher-SUMMARY.md
@.planning/phases/02-provider-protocol-greenhouse-dispatcher-observability/02-02-greenhouse-SUMMARY.md
@.planning/phases/01-schema-migration-paths-foundational-cleanup/01-03-docs-SUMMARY.md
@skills/scout-run/SKILL.md
@skills/job-scout/references/file-contract.md
@scripts/ats/__init__.py
@scripts/ats/dispatcher.py
@scripts/ats/runs_log.py

<interfaces>
<!-- Plan 02-01 + 02-02 contracts that preview.py imports directly -->

dispatcher.py (Plan 02-01) — programmatic API used by preview.py:
```python
from ats.dispatcher import fetch_all, aggregate_outcomes, FetchOutcome
# fetch_all(targets: List[Tuple[str, str]], config_path: str) -> List[FetchOutcome]
# fetch_all OWNS the httpx.Client lifetime: instantiates once, closes in `finally`
# (DSP-03 contract — verified in 02-01 dispatcher.py docstring + Task 3 verify)
# aggregate_outcomes(outcomes) -> (per_provider_outcomes, per_company_provider, per_provider_listings)
# FetchOutcome attrs: company_slug, provider, outcome (RunOutcome enum), listings, raw, http_status, error, elapsed_seconds
```

runs_log.py (Plan 02-01) — programmatic API used by preview.py:
```python
from ats.runs_log import append_run, RunOutcome
# append_run(runs_log_path, wall_clock_seconds, per_provider_outcomes, per_company_provider, per_provider_listings, timestamp=None) -> dict
```

dispatcher.py CLI (Plan 02-01) — NOT used by preview.py; kept for ad-hoc debugging only:
```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/dispatcher.py fetch-all <config.json> <targets.json>
```

<!-- Phase 1 paths already in file-contract.md (do NOT add new entries here) -->

`<data_dir>/runs.jsonl` — Phase 1 SCH-01; created by validate_data.py:validate_runs_log
`<data_dir>/daily/<DATE>/ats_raw/` — Phase 1 SCH-02; created by validate_data.py:ensure_today_subdirs

DSP-10 conventionally writes ats_raw/<provider>/<company>.json — i.e. one MORE level of nesting under ats_raw/. The `ats_raw/<provider>/` subdirectory is created on-demand by preview.py via os.makedirs(..., exist_ok=True).

<!-- The user's pending uncommitted edits to skills/scout-run/SKILL.md -->

`git diff skills/scout-run/SKILL.md` at start of Plan 02-03 execution shows:
- Hunk 1: frontmatter line 5: `version: 0.3.1` → `version: 0.3.3`
- Hunk 2: Step 2 lines around 87-93: replaces "LinkedIn company jobs tab" bullet (the old `f_C` filter approach that's broken) with the keyword-search URL pattern + the rationale paragraph about f_C being broken/disabled

These hunks are AT DIFFERENT LINES than Plan 02-03's edit (which inserts Step 2.5 around line 109+ of the working tree). No actual conflict. But because the working tree has uncommitted changes, a naive `git add skills/scout-run/SKILL.md` would commit the user's edits along with ours. The protocol (validated by Plan 01-03) prevents this:

```bash
# Step A: detect pending edits
if ! git diff --quiet skills/scout-run/SKILL.md; then
    HAS_PENDING=1
fi

# Step B: snapshot the working tree (with user's edits) to /tmp
cp skills/scout-run/SKILL.md /tmp/scout-run-SKILL-with-user-edits-DSP10.md

# Step C: reset the working tree to HEAD (drop user's edits temporarily)
git checkout HEAD -- skills/scout-run/SKILL.md

# Step D: apply ONLY Plan 02-03's edit on the clean base (use Edit tool against
# the HEAD version of the file)

# Step E: commit
git add skills/scout-run/SKILL.md
git commit -m "feat(02-03): add [ATS-PREVIEW] Pass 1 hook to /scout-run Step 2.5 (DSP-10)"

# Step F: restore the user's pending edits ON TOP of the new HEAD
```

The corrected protocol (which is what Plan 01-03 actually documented and what we use here):

1. **Detect:** `if ! git diff --quiet skills/scout-run/SKILL.md; then HAS_PENDING=1; fi`
2. **Snapshot:** `cp skills/scout-run/SKILL.md /tmp/scout-run-SKILL-pre-DSP10.md`
3. **Reset to HEAD:** `git checkout HEAD -- skills/scout-run/SKILL.md`
4. **Apply Plan 02-03's edit** to the HEAD-clean file via the Edit tool. Stage + commit.
5. **Restore user's edits:** `cp /tmp/scout-run-SKILL-pre-DSP10.md skills/scout-run/SKILL.md`. This OVERWRITES the new commit's content with the snapshot — losing Plan 02-03's edit from the working tree. So...
6. **Re-apply Plan 02-03's edit** ON TOP of the now-restored working tree, using the Edit tool again. The user's pending edits at frontmatter line 5 + Step 2 lines 87-93 are still in the working tree; Plan 02-03's edit at the new Step 2.5 offset (after end of Step 2, before Step 3) inserts cleanly because the anchor `## Step 3: Pass 2 — Other job boards` is identical in both versions.
7. **Verify:** `git status` should show `skills/scout-run/SKILL.md` modified with BOTH the user's pending edits AND Plan 02-03's edit. The new commit (from step 4) is still in `git log`. The working tree shows the user's pending state restored on top.

Plan 01-03 successfully executed this exact protocol against this file in commit 2e84994 — see `.planning/phases/01-schema-migration-paths-foundational-cleanup/01-03-docs-SUMMARY.md` line 19 for the post-mortem.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create scripts/ats/preview.py — single-fetch_all driver script</name>
  <files>scripts/ats/preview.py</files>
  <read_first>
    Read ONCE:
    1. scripts/ats/dispatcher.py (Plan 02-01 — for fetch_all, aggregate_outcomes, FetchOutcome shape).
    2. scripts/ats/runs_log.py (Plan 02-01 — for append_run, RunOutcome).
    3. scripts/ats/__init__.py (Plan 02-01 — for sibling-bootstrap pattern + PROVIDERS registry).
    4. scripts/state.py (existing — for the CLI subcommand dispatch shape via sys.argv).

    Do NOT read anything else. The interfaces table above already includes the relevant function signatures.
  </read_first>
  <action>
    Create `scripts/ats/preview.py`. Use the Write tool (never heredoc).

    Module docstring (verbatim opener):
    ```python
    """
    preview.py — Phase 2 [ATS-PREVIEW] driver. ONE process invocation per /scout-run.

    Why a separate driver script and not three SKILL bash steps?

    DSP-03 (locked Phase 2 decision): exactly ONE shared httpx.Client per /scout-run.
    The dispatcher's fetch_all() owns that Client's lifetime via `with httpx.Client(...)`.
    If the SKILL prompt called fetch_all() three times (once for the dispatcher CLI,
    once to persist raw payloads, once to append runs.jsonl), each invocation
    would instantiate ITS OWN Client — three Clients per run, three round-trips
    against every Greenhouse company, three contributions toward the 5-min budget,
    and the wall_clock_seconds in runs.jsonl would reflect only the LAST call's
    time. That violates DSP-03.

    Solution: this driver collapses all three responsibilities into ONE process,
    so the SKILL invokes ONE CLI command and ONE httpx.Client is opened.

    Usage (called from skills/scout-run/SKILL.md Step 2.5):

        python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/preview.py <data_dir> <TODAY> <slugs_csv>

    Where:
      <data_dir>   absolute path to user's data dir (e.g. ~/Documents/JobSearch).
      <TODAY>      ISO date for today's run (e.g. "2026-04-28").
      <slugs_csv>  comma-separated company slugs to fetch from Greenhouse
                   (the SKILL has already filtered master_targets.csv rows
                   where ats_provider == "greenhouse" and derived the slugs
                   from ats_board_url).

    Behavior (in order, in a SINGLE process):
      1. Build targets list: [(slug, "greenhouse") for slug in slugs].
      2. Call dispatcher.fetch_all(targets, <data_dir>/config.json) ONCE.
         (fetch_all owns the httpx.Client; instantiated once, closed in `finally`.)
      3. For every OK_WITH_RESULTS outcome, persist its raw payload to
         <data_dir>/daily/<TODAY>/ats_raw/<provider>/<slug>.json.
      4. Aggregate outcomes via dispatcher.aggregate_outcomes().
      5. Append ONE runs.jsonl line via runs_log.append_run() with the
         wall_clock measured around step 2 (the actual fetch_all duration —
         not preview.py's startup or the json.dump in step 3).
      6. Print to stdout a JSON summary the SKILL parses for the report:
         {
           "outcome_count": N,
           "wall_clock_seconds": X,
           "per_provider_outcomes": {...},
           "per_company_provider": {...},
           "ok_with_results_companies": ["airbnb", ...],
           "raw_persisted": {"<provider>/<slug>.json": <listings_count>, ...}
         }

    --help and --version smoke flags supported for verify-time sanity.

    Phase 5 will fold this back into a single end-of-/scout-run append once
    Pass 2 dedup lands; Phase 2's per-block append is acceptable because the
    [ATS-PREVIEW] flow is the only ATS path in this milestone.
    """
    import json
    import os
    import sys
    import time
    from typing import Any, Dict, List, Tuple
    ```

    Sibling bootstrap (2-level — file → ats → scripts; matches dispatcher.py / runs_log.py from Plan 02-01):
    ```python
    SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)

    # Imports from sibling modules within the ats package. dispatcher.py
    # already handles the httpx ImportError block — preview.py inherits that
    # error reporting by importing fetch_all (which lives in dispatcher.py).
    from ats.dispatcher import fetch_all, aggregate_outcomes
    from ats.runs_log import append_run, RunOutcome
    ```

    Public function (kept as a function so future tests can call it without subprocess'ing the CLI):
    ```python
    def run_preview(
        data_dir: str,
        today: str,
        slugs: List[str],
        provider: str = "greenhouse",
    ) -> Dict[str, Any]:
        """Run a single Phase 2 [ATS-PREVIEW] cycle and return the summary dict.

        Args:
            data_dir: absolute path; caller has already expanded ~.
            today:    ISO date string (e.g. "2026-04-28") — already validated by SKILL.
            slugs:    list of Greenhouse company slugs from master_targets.csv
                      (already filtered to ats_provider == "greenhouse" + non-empty
                      ats_board_url; slug derived from ats_board_url path tail).
            provider: hardcoded "greenhouse" in Phase 2 — kept as a parameter so
                      Phase 4 can extend with the other 4 providers without
                      changing the function signature.

        Returns: a dict suitable for json.dump to stdout (the SKILL reads it
                 to render the [ATS-PREVIEW] block in Step 6).

        Side effects:
            - Writes <data_dir>/daily/<today>/ats_raw/<provider>/<slug>.json
              for every OK_WITH_RESULTS outcome (one file per company).
            - Appends one line to <data_dir>/runs.jsonl with the run's stats.

        Raises (these are intentional — preview.py exits non-zero so the SKILL
                does NOT swallow them):
            FileNotFoundError: <data_dir>/config.json missing (Phase 1's
                validate_data.py should have ensured this; the error is loud
                so a misconfigured data_dir is visible).
            httpx ImportError: surfaced by dispatcher.py at import time.
        """
        config_path = os.path.join(data_dir, "config.json")
        if not os.path.isfile(config_path):
            # Loud + actionable; preview.py is invoked from the SKILL prompt and
            # the user can't see Python tracebacks easily — print the path.
            print(
                f"ERROR: {config_path} not found. "
                f"Run /scout-setup once to create it. "
                f"Phase 1's validate_data.py is responsible for ensuring this exists.",
                file=sys.stderr,
            )
            raise FileNotFoundError(config_path)

        runs_log_path = os.path.join(data_dir, "runs.jsonl")
        ats_raw_dir = os.path.join(data_dir, "daily", today, "ats_raw")

        # Build targets list. Empty input is fine — fetch_all returns [].
        targets: List[Tuple[str, str]] = [(slug, provider) for slug in slugs if slug]

        # ONE fetch_all call. fetch_all instantiates and closes the httpx.Client
        # internally (DSP-03). We measure wall-clock around THIS line — that's
        # what runs.jsonl reflects.
        t0 = time.monotonic()
        outcomes = fetch_all(targets, config_path)
        wall_clock = time.monotonic() - t0

        # Persist raw payloads from the SAME outcomes (no second fetch).
        raw_persisted: Dict[str, int] = {}
        ok_companies: List[str] = []
        for o in outcomes:
            if o.outcome != RunOutcome.OK_WITH_RESULTS:
                continue
            ok_companies.append(o.company_slug)
            provider_dir = os.path.join(ats_raw_dir, o.provider)
            os.makedirs(provider_dir, exist_ok=True)
            raw_path = os.path.join(provider_dir, f"{o.company_slug}.json")
            payload = {
                "company_slug": o.company_slug,
                "provider": o.provider,
                "http_status": o.http_status,
                "elapsed_seconds": round(o.elapsed_seconds, 3),
                "raw": o.raw,
                "listings": [L.to_dict() for L in o.listings],
            }
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            raw_persisted[f"{o.provider}/{o.company_slug}.json"] = len(o.listings)

        # Aggregate from the SAME outcomes — no second fetch.
        per_provider, per_company_provider, per_provider_listings = aggregate_outcomes(outcomes)

        # ONE runs.jsonl append from the SAME outcomes.
        line = append_run(
            runs_log_path=runs_log_path,
            wall_clock_seconds=wall_clock,
            per_provider_outcomes=per_provider,
            per_company_provider=per_company_provider,
            per_provider_listings=per_provider_listings,
        )

        return {
            "outcome_count": len(outcomes),
            "wall_clock_seconds": round(wall_clock, 3),
            "per_provider_outcomes": per_provider,
            "per_company_provider": per_company_provider,
            "ok_with_results_companies": ok_companies,
            "raw_persisted": raw_persisted,
            "runs_jsonl_line": line,
        }
    ```

    CLI dispatch (matches state.py / tracker_utils.py shape — single-command, positional args):
    ```python
    if __name__ == "__main__":
        # --help / --version smoke flags (verify-time sanity)
        if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help"):
            print(
                "Usage: python3 scripts/ats/preview.py <data_dir> <TODAY> <slugs_csv>\n"
                "\n"
                "Run a single Phase 2 [ATS-PREVIEW] cycle for /scout-run Step 2.5.\n"
                "ONE process → ONE fetch_all → ONE httpx.Client → ONE runs.jsonl append.\n"
                "\n"
                "Args:\n"
                "  <data_dir>   absolute path to user's data dir (~ already expanded by caller).\n"
                "  <TODAY>      ISO date string for today's run (e.g. 2026-04-28).\n"
                "  <slugs_csv>  comma-separated Greenhouse company slugs.\n"
                "               Empty string is OK — runs the empty-targets path\n"
                "               (still appends a runs.jsonl line with 0 outcomes).\n"
            )
            sys.exit(0)
        if len(sys.argv) >= 2 and sys.argv[1] == "--version":
            print("preview.py: Phase 2 DSP-10 driver, v0.4")
            sys.exit(0)

        if len(sys.argv) < 4:
            print(
                "Usage: python3 scripts/ats/preview.py <data_dir> <TODAY> <slugs_csv>",
                file=sys.stderr,
            )
            sys.exit(1)

        data_dir = os.path.expanduser(sys.argv[1])
        today = sys.argv[2]
        slugs_csv = sys.argv[3]
        slugs = [s.strip() for s in slugs_csv.split(",") if s.strip()]

        try:
            summary = run_preview(data_dir, today, slugs)
        except FileNotFoundError:
            sys.exit(2)

        # Drop the runs_jsonl_line from the printed summary — it's the same
        # info structure but the line is large, and the SKILL only needs the
        # aggregates + raw-persisted manifest.
        printable = {k: v for k, v in summary.items() if k != "runs_jsonl_line"}
        print(json.dumps(printable, indent=2, ensure_ascii=False))
        sys.exit(0)
    ```

    NO Pythonic dependencies beyond stdlib + dispatcher + runs_log (which already declare httpx). preview.py adds zero new third-party imports.
  </action>
  <verify>
    <automated>
test -f scripts/ats/preview.py && \
grep -q "def run_preview" scripts/ats/preview.py && \
grep -q "from ats.dispatcher import fetch_all" scripts/ats/preview.py && \
grep -q "from ats.runs_log import append_run" scripts/ats/preview.py && \
grep -q "fetch_all(targets, config_path)" scripts/ats/preview.py && \
# Exactly ONE fetch_all call in the whole module (DSP-03 — single-call invariant)
test "$(grep -c 'fetch_all(' scripts/ats/preview.py)" -le 2 && \
# (--help and the actual call may both substring-match; the CALL site is unique)
~/.job-scout-venv/bin/python3 ${PWD}/scripts/ats/preview.py --help | grep -q "ONE process" && \
~/.job-scout-venv/bin/python3 ${PWD}/scripts/ats/preview.py --version | grep -q "Phase 2" && \
~/.job-scout-venv/bin/python3 -c "
import sys, os, tempfile, json
sys.path.insert(0, 'scripts')
from ats.preview import run_preview
# Empty-slugs roundtrip (no network) — still appends a runs.jsonl line with 0 outcomes
with tempfile.TemporaryDirectory() as td:
    cfg = os.path.join(td, 'config.json')
    json.dump({'ats': {}}, open(cfg, 'w'))
    runs_log = os.path.join(td, 'runs.jsonl')
    open(runs_log, 'w').close()
    today = '2026-04-28'
    daily = os.path.join(td, 'daily', today, 'ats_raw')
    os.makedirs(daily, exist_ok=True)
    summary = run_preview(td, today, [])
    assert summary['outcome_count'] == 0, summary
    assert summary['per_provider_outcomes'] == {}
    assert summary['raw_persisted'] == {}
    # runs.jsonl was appended exactly once
    with open(runs_log) as f:
        lines = [L for L in f if L.strip()]
    assert len(lines) == 1, f'expected 1 runs.jsonl line, got {len(lines)}'
    # And the line carries the wall_clock from the SAME fetch_all call
    line = json.loads(lines[0])
    assert 'wall_clock_seconds' in line
    assert line['providers'] == {}
print('Task 1 OK: preview.py single-fetch_all roundtrip works on empty input')
"
    </automated>
  </verify>
  <done>
    scripts/ats/preview.py exists with `run_preview()` function + CLI entry point. ONE fetch_all call in the function body. --help / --version smoke flags work. Empty-slugs roundtrip appends exactly ONE runs.jsonl line and writes ZERO ats_raw files (no OK_WITH_RESULTS outcomes). Commit: `feat(02-03): add scripts/ats/preview.py — single-fetch_all driver for [ATS-PREVIEW] (DSP-10)`.
  </done>
</task>

<task type="auto">
  <name>Task 2: Detect + snapshot user's pending uncommitted edits to scout-run/SKILL.md</name>
  <files></files>
  <read_first>
    Read ONCE:
    1. .planning/phases/01-schema-migration-paths-foundational-cleanup/01-03-docs-SUMMARY.md (post-mortem of the same protocol — already in context).
    2. CURRENT working-tree state of skills/scout-run/SKILL.md (NOT just HEAD — the user has uncommitted edits).
  </read_first>
  <action>
    No file edits in this task — pure protocol setup.

    Run these bash commands SEQUENTIALLY (one bash invocation, chained with `&&`):

    ```bash
    # 1. Confirm we're in the plugin root
    test -f .claude-plugin/plugin.json && \
    test -f skills/scout-run/SKILL.md && \

    # 2. Detect pending edits — git diff --quiet exits 1 if there are uncommitted changes
    if git diff --quiet skills/scout-run/SKILL.md; then
        echo "TASK 2: NO pending edits to skills/scout-run/SKILL.md — protocol simplified to a normal edit."
        echo "TASK 2 STATE: HAS_PENDING=0"
    else
        # 3. Snapshot the current (with-user-edits) state
        cp skills/scout-run/SKILL.md /tmp/scout-run-SKILL-pre-DSP10.md
        # 4. Verify snapshot is intact
        if ! diff -q skills/scout-run/SKILL.md /tmp/scout-run-SKILL-pre-DSP10.md >/dev/null; then
            echo "ERROR: snapshot diff failed — abort plan execution" >&2
            exit 1
        fi
        # 5. Capture the diff against HEAD so we have the exact pending hunks for verification later
        git diff skills/scout-run/SKILL.md > /tmp/scout-run-SKILL-pending-DSP10.diff
        wc -l /tmp/scout-run-SKILL-pending-DSP10.diff
        echo "TASK 2: pending edits snapshotted to /tmp/scout-run-SKILL-pre-DSP10.md"
        echo "TASK 2 STATE: HAS_PENDING=1"
    fi
    ```

    The output tells the executor whether to use the full stash-replay protocol (HAS_PENDING=1, follow Tasks 3 + 4) or a simplified flow (HAS_PENDING=0, Task 3 becomes a normal Edit + commit, Task 4 becomes a no-op).

    DO NOT run any other commands. DO NOT edit skills/scout-run/SKILL.md yet. DO NOT git add or commit anything.

    NOTE: per the planning_context, the user IS expected to have pending edits at session start (per "pending uncommitted edits to skills/scout-run/SKILL.md: 2 pending hunks — frontmatter version 0.3.3 + Step 2 LinkedIn URL pattern"). The HAS_PENDING=0 path is the safety branch in case the user has committed those edits between planning and execution.
  </action>
  <verify>
    <automated>
# Verify the snapshot file exists OR the no-pending message printed.
test -f /tmp/scout-run-SKILL-pre-DSP10.md || git diff --quiet skills/scout-run/SKILL.md
    </automated>
  </verify>
  <done>
    Either /tmp/scout-run-SKILL-pre-DSP10.md exists (HAS_PENDING=1) and is byte-identical to the pre-task working tree, or git diff --quiet returns 0 (HAS_PENDING=0). The HAS_PENDING state is captured in stdout for the next task. NO commits.
  </done>
</task>

<task type="auto">
  <name>Task 3: Reset to HEAD, apply Plan 02-03's [ATS-PREVIEW] edit, commit on a clean base</name>
  <files>skills/scout-run/SKILL.md</files>
  <read_first>
    Read skills/scout-run/SKILL.md as it exists in HEAD (NOT the working tree). Use:
    ```bash
    git show HEAD:skills/scout-run/SKILL.md > /tmp/scout-run-SKILL-HEAD-DSP10.md
    ```
    Then Read /tmp/scout-run-SKILL-HEAD-DSP10.md ONCE to confirm anchor lines (the `## Step 2: Pass 1` heading and the `## Step 3: Pass 2 — Other job boards` heading flank the insertion point).

    NOTE: Reading the working tree of the file would mix in the user's pending edits, which is what we're explicitly trying to avoid. The HEAD-only read confirms the anchor for the Edit tool's `old_string` matching.
  </read_first>
  <action>
    **Step A: Reset working tree to HEAD** (drops user's pending edits temporarily — they're safe in /tmp from Task 2).

    ```bash
    if test -f /tmp/scout-run-SKILL-pre-DSP10.md; then
        # Pending edits were snapshotted in Task 2
        git checkout HEAD -- skills/scout-run/SKILL.md
    fi
    # If no pending edits (HAS_PENDING=0), no checkout needed — working tree IS HEAD
    ```

    **Step B: Apply the Plan 02-03 edit using the Edit tool.**

    The edit inserts a new `## Step 2.5: [ATS-PREVIEW] Pass 1 (Greenhouse only)` block BETWEEN the existing Step 2 (last line of which is around: "If Pass 1 finishes under-budget, do NOT roll the leftover budget into Pass 2 or Pass 3. Under-budget here means there genuinely wasn't enough company-side activity worth tracking; Passes 2 and 3 won't fix that.") AND the existing Step 3 heading (`## Step 3: Pass 2 — Other job boards (≈25% of budget)`).

    Use the Edit tool. The `old_string` is the existing `## Step 3` heading line + a few lines of context to disambiguate (matching just `## Step 3:` could collide elsewhere). The `new_string` inserts the new Step 2.5 block FIRST, then the unchanged Step 3 heading.

    `old_string` (verbatim — copy from the HEAD-version file Read above; using the heading + 1 leading separator as anchor):
    ```
    ---

    ## Step 3: Pass 2 — Other job boards (≈25% of budget)
    ```

    `new_string` (verbatim — inserts Step 2.5 + restores the unchanged Step 3 anchor):
    ```
    ---

    ## Step 2.5: [ATS-PREVIEW] Pass 1 (Greenhouse only) — additive

    **What this is:** Phase 2 of the v0.4 ATS-first migration ships a structured ATS query path (Provider Protocol + dispatcher + runs.jsonl observability) and wires Greenhouse-only fetches into `/scout-run` ADDITIVELY. The existing 3-pass flow above (Pass 1 / Pass 2 / Pass 3) still runs and still produces output. This block adds an `[ATS-PREVIEW]` slice — its listings are tagged in Step 6's report so they're visible without changing scoring or tier assignment. **Phase 5 will replace the old flow; until then, both run.** Do not interpret the [ATS-PREVIEW] tag as scoring authority.

    **Pre-conditions** (Phase 1 already guarantees):
    - `<data_dir>/runs.jsonl` exists (created by `validate_data.py:validate_runs_log` — Step 0 step 2 above already ran).
    - `<data_dir>/daily/<TODAY>/ats_raw/` exists (created by `validate_data.py ensure-today` — Step 0 step 4 above already ran).

    **Architectural invariant — ONE process per /scout-run.** Per DSP-03 (locked), the dispatcher uses ONE shared `httpx.Client` per run. To honor that at the SKILL boundary, all three responsibilities — invoke the dispatcher, persist raw payloads, append `runs.jsonl` — live inside `scripts/ats/preview.py` and the SKILL invokes it with EXACTLY ONE Bash call.

    1. **Build the slug list.** Read `master_targets.csv` columns `company_name`, `ats_provider`, `ats_board_url` (already in scope from Step 0). Filter to rows where `ats_provider == "greenhouse"` AND `ats_board_url` is non-empty. For each kept row, derive the company slug from `ats_board_url`:
       - `https://boards.greenhouse.io/<slug>` → `<slug>`
       - `https://boards-api.greenhouse.io/v1/boards/<slug>` → `<slug>`
       - `https://job-boards.greenhouse.io/<slug>` → `<slug>`

       Build a comma-separated string `<slugs_csv>`. If no rows qualify (e.g. fresh master_targets.csv with no `ats_provider` populated yet — typical until Phase 3 ships `/scout-detect`), still invoke `preview.py` with `<slugs_csv>=""` so a `runs.jsonl` line is appended (with 0 outcomes — Phase 5's regression-suspect logic needs the daily heartbeat). Print `[ATS-PREVIEW] No Greenhouse companies in master_targets.csv (Phase 3 will populate via /scout-detect).` to stdout for visibility.

    2. **Invoke the [ATS-PREVIEW] driver — ONE Bash call.**
       ```bash
       python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/preview.py "<data_dir>" "<TODAY>" "<slugs_csv>"
       ```
       This single process:
       - opens ONE `httpx.Client` (DSP-03 contract preserved);
       - calls `dispatcher.fetch_all` ONCE;
       - persists raw payloads from each `OK_WITH_RESULTS` outcome to `<data_dir>/daily/<TODAY>/ats_raw/greenhouse/<company>.json`;
       - appends ONE line to `<data_dir>/runs.jsonl` via `runs_log.append_run` (DSP-07);
       - prints a JSON summary to stdout with `outcome_count`, `wall_clock_seconds`, `per_provider_outcomes`, `per_company_provider`, `ok_with_results_companies`, and `raw_persisted` (a manifest of which raw files were written and how many listings each contains).

       Capture stdout — the SKILL parses it to render the [ATS-PREVIEW] block in Step 6.

    3. **Render in the report.** In Step 6 below, for any company in the `ok_with_results_companies` list from the JSON summary, read `<data_dir>/daily/<TODAY>/ats_raw/greenhouse/<company>.json` (each file has a `listings[]` array of canonical Listing dicts). Render under a new `### [ATS-PREVIEW] Greenhouse listings` section with this minimal block per listing:
       ```
       - **Company:** <company_name>
       - **Title:** <title>
       - **Apply:** <url>
       - **Posted:** <posted_date>
       - **Source:** ats:greenhouse
       - **[ATS-PREVIEW]** This is Phase 2 plumbing. Not scored, not tier-assigned. Phase 5 will hoist into Pass 1 with the +1 ATS bump.
       ```
       The existing A/B/C tier blocks in Step 6 are unchanged — this is a NEW section appended after the existing Honest notes section.

    **Failure modes the dispatcher already handles (no skill-side handling needed):**
    - 404 / unknown slug → bucketed as ERROR in runs.jsonl with the http_status; the company silently does not contribute to [ATS-PREVIEW]. Phase 5 surfaces "ATS regression suspect" warnings from runs.jsonl.
    - 200 + 0 jobs → bucketed as OK_ZERO; Phase 5 surfaces this distinguishably from ERROR.
    - Network failure / timeout → bucketed as ERROR with the exception class+message in runs.jsonl.
    - Provider mapper raises ValueError on missing required field → caught by dispatcher's worker wrapper; bucketed as ERROR; the bad job is in raw[] for replay but not in listings[].
    - `<data_dir>/config.json` missing → preview.py exits 2 with a printed message; the SKILL surfaces this as a setup error and skips Steps 3/4/5/6 of the [ATS-PREVIEW] block (the Pass 2/Pass 3 / report flow continues unaffected).

    ---

    ## Step 3: Pass 2 — Other job boards (≈25% of budget)
    ```

    Use the Edit tool ONCE with this old_string / new_string pair. The Edit tool will fail loudly if the old_string is not unique — verify that the `## Step 3: Pass 2 — Other job boards (≈25% of budget)` line appears exactly once in the file before invoking.

    **Step C: Stage and commit.**

    ```bash
    git add skills/scout-run/SKILL.md
    git commit -m "feat(02-03): add [ATS-PREVIEW] Pass 1 hook to /scout-run Step 2.5 (DSP-10)

Wires Plan 02-01's dispatcher + Plan 02-02's Greenhouse provider into
/scout-run as a NEW Step 2.5 — additively, alongside the existing 3-pass
flow. Old output unchanged. New output tagged [ATS-PREVIEW] in Step 6.

The SKILL invokes scripts/ats/preview.py with ONE Bash call per run —
that single process opens ONE httpx.Client, calls fetch_all ONCE,
persists raw payloads, and appends ONE runs.jsonl line, all from the
SAME outcomes. DSP-03 (single shared Client) preserved at the SKILL
boundary.

Per DSP-10 locked decision: Phase 2 does not change scoring or tier
assignment. Phase 5 hoists ATS into Pass 1 anchor with +1 tier bump."
    ```

    The commit is on a clean (HEAD-based) tree — the user's pending edits are still in /tmp from Task 2, ready to be restored in Task 4.
  </action>
  <verify>
    <automated>
# 1. Commit landed
git log --oneline -1 | grep -q "feat(02-03):" && \
# 2. The committed file has the new Step 2.5 block
git show HEAD:skills/scout-run/SKILL.md | grep -q "## Step 2.5: \[ATS-PREVIEW\]" && \
git show HEAD:skills/scout-run/SKILL.md | grep -q "ats_raw" && \
# 3. The committed file references the preview.py driver (the single CLI invocation)
git show HEAD:skills/scout-run/SKILL.md | grep -q "scripts/ats/preview.py" && \
# 4. The committed file references the ats.runs_log Python module path (used by preview.py)
#    via the inserted prose ("appends ONE line to <data_dir>/runs.jsonl via runs_log.append_run")
git show HEAD:skills/scout-run/SKILL.md | grep -q "runs_log.append_run" && \
# 5. The committed file does NOT contain three separate inline-Python heredocs calling fetch_all
#    (DSP-03 single-call invariant — the old design called fetch_all 3 times per run).
test "$(git show HEAD:skills/scout-run/SKILL.md | grep -c 'fetch_all(')" -eq 0 && \
# 6. The committed file does NOT contain the user's pending edits
# This check is conditional: only assert if Task 2 captured pending edits
if test -f /tmp/scout-run-SKILL-pre-DSP10.md; then
    # The commit must NOT include the user's pending hunks. Diff the committed
    # version against the original HEAD (one commit back) and confirm only
    # Plan 02-03's hunks are present.
    git diff HEAD~1 HEAD -- skills/scout-run/SKILL.md | grep -q "+## Step 2.5: \[ATS-PREVIEW\]"
    # And confirm the user's f_C-disabled hunk is NOT in this commit
    if git diff HEAD~1 HEAD -- skills/scout-run/SKILL.md | grep -q "f_C.*disabled\|broken.*f_C"; then
        echo "ERROR: Plan 02-03 commit contains the user's pending f_C hunk — protocol failure" >&2
        exit 1
    fi
fi && \
echo "TASK 3 OK"
    </automated>
  </verify>
  <done>
    Plan 02-03's commit exists in `git log`. The committed `skills/scout-run/SKILL.md` contains the new Step 2.5 block referencing `scripts/ats/preview.py` (single CLI invocation) + `runs_log.append_run` + `ats_raw` paths, and does NOT contain any inline `fetch_all(` calls (DSP-03 single-call invariant enforced at the SKILL layer). The commit does NOT contain the user's pending hunks (frontmatter 0.3.3 or the f_C-broken rationale). The working tree is currently at this commit's content (user's edits not yet restored — Task 4 does that).
  </done>
</task>

<task type="auto">
  <name>Task 4: Restore user's pending edits + re-apply Plan 02-03's edit on top</name>
  <files>skills/scout-run/SKILL.md</files>
  <read_first>
    Re-read /tmp/scout-run-SKILL-pre-DSP10.md ONCE to confirm it still exists (it should — it's untouched since Task 2).

    Re-read the post-commit working-tree state of skills/scout-run/SKILL.md ONCE to confirm Task 3's commit landed cleanly.
  </read_first>
  <action>
    Skip this task entirely if Task 2 reported `HAS_PENDING=0` (no pending edits → nothing to restore). Otherwise:

    **Step A: Restore the user's pending edits to the working tree.**

    ```bash
    if test -f /tmp/scout-run-SKILL-pre-DSP10.md; then
        cp /tmp/scout-run-SKILL-pre-DSP10.md skills/scout-run/SKILL.md
        # The working tree is now: HEAD (= Plan 02-03 commit) BUT with content
        # replaced by the original pre-Task-2 snapshot, which is HEAD~1 + user's
        # pending edits. So `git diff HEAD` will show:
        #   - Plan 02-03's Step 2.5 block REMOVED (because the snapshot is from
        #     before that commit landed)
        #   - User's pending hunks ADDED (frontmatter 0.3.3 + f_C-disabled)
        # We need to RE-INSERT Plan 02-03's Step 2.5 block on top of the
        # restored user-edited tree.
    fi
    ```

    **Step B: Re-apply Plan 02-03's Step 2.5 edit on top of the restored user edits.**

    Use the Edit tool with the SAME `old_string` / `new_string` pair from Task 3 — the anchor (`## Step 3: Pass 2 — Other job boards (≈25% of budget)`) is identical in HEAD and in the user's snapshot, so the Edit tool finds and inserts cleanly. The user's pending edits at frontmatter line 5 + Step 2 lines 87-93 are at different offsets and untouched.

    **Step C: Verify final state.**

    ```bash
    # Final state: working tree has BOTH Plan 02-03's Step 2.5 AND the user's
    # pending hunks. The Plan 02-03 commit is in git log. The user's hunks
    # remain uncommitted (git status shows skills/scout-run/SKILL.md modified).

    # 1. Plan 02-03's edit is in the working tree (the file Claude reads)
    grep -q "## Step 2.5: \[ATS-PREVIEW\]" skills/scout-run/SKILL.md && \
    # 2. User's pending hunks are in the working tree (frontmatter 0.3.3)
    grep -q "^version: 0.3.3" skills/scout-run/SKILL.md && \
    # 3. User's pending hunks are in the working tree (LinkedIn URL pattern with f_C disabled rationale)
    grep -q "f_C.*disabled\|f_C.*broken\|f_C.*unreliable" skills/scout-run/SKILL.md && \
    # 4. git status shows uncommitted modifications (the user's hunks)
    git status --porcelain skills/scout-run/SKILL.md | grep -qE "^.M" && \
    # 5. The HEAD commit has Plan 02-03's edit (sanity check — HEAD didn't move)
    git log --oneline -1 | grep -q "feat(02-03):"
    ```

    If all 5 lines pass, the protocol succeeded:
    - Plan 02-03's edit is committed in HEAD.
    - User's pending edits are restored on top, still uncommitted, EXACTLY as they were at session start.
    - The working tree shows BOTH so future runs of `/scout-run` see the merged content.

    **Step D: Clean up /tmp.**

    ```bash
    rm -f /tmp/scout-run-SKILL-pre-DSP10.md /tmp/scout-run-SKILL-pending-DSP10.diff /tmp/scout-run-SKILL-HEAD-DSP10.md
    ```

    The /tmp files are no longer needed. They were the protocol's intermediate state.

    DO NOT run `git add` or `git commit` for the user's pending edits — they belong to the user and should remain uncommitted, exactly as they were at session start. The user will commit them when they're ready, in their own commit, separate from Plan 02-03's commit.
  </action>
  <verify>
    <automated>
# Final-state assertions (the same 5 from Step C; re-run for the gate):
grep -q "## Step 2.5: \[ATS-PREVIEW\]" skills/scout-run/SKILL.md && \
echo "  -> Plan 02-03's Step 2.5 in working tree: OK" && \
# Conditional: only assert user-pending state if Task 2 had pending edits
if ! test -f /tmp/scout-run-SKILL-pre-DSP10.md && git diff --quiet skills/scout-run/SKILL.md; then
    # Either no pending edits at session start (HAS_PENDING=0) or they were already restored cleanly
    echo "  -> No pending user edits / clean working tree: OK"
elif git status --porcelain skills/scout-run/SKILL.md | grep -qE "^.M"; then
    grep -q "^version: 0.3.3" skills/scout-run/SKILL.md && \
    grep -qE "f_C.*disabled|f_C.*broken|f_C.*unreliable|Do NOT use LinkedIn's .f_C" skills/scout-run/SKILL.md && \
    echo "  -> User's pending edits restored on top: OK"
else
    echo "ERROR: post-Task-4 state inconsistent — pending state expected but file is clean against HEAD" >&2
    exit 1
fi && \
git log --oneline -1 | grep -q "feat(02-03):" && \
echo "  -> HEAD has Plan 02-03 commit: OK" && \
# /tmp cleanup verified (files should be gone)
test ! -f /tmp/scout-run-SKILL-pre-DSP10.md && \
echo "  -> /tmp cleanup OK" && \
echo "TASK 4 OK: protocol complete"
    </automated>
  </verify>
  <done>
    Working tree has Plan 02-03's [ATS-PREVIEW] block AND the user's pending uncommitted hunks (frontmatter 0.3.3 + f_C-disabled rationale). HEAD commit is Plan 02-03's `feat(02-03):` commit. `git status` shows skills/scout-run/SKILL.md modified (the user's hunks). The /tmp protocol files are cleaned up. NO additional commits beyond Plan 02-03's. The user's pending edits are at the EXACT same shape they were at session start — verifiable by diffing the saved snapshot before Task 2 deletion (already done as part of Task 2's snapshot integrity check).
  </done>
</task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Plan 02-03 edit → user's working tree | Mutates a file the user has uncommitted edits in; protocol must preserve user's content. |
| preview.py CLI shell call → /scout-run | Subprocess invoked from skill markdown; arguments are validated paths inside `<data_dir>` (no untrusted input crossing). |
| ats_raw/ writes → user's data dir | Files written under `<data_dir>/daily/<TODAY>/ats_raw/<provider>/`; respects 0o700 perms inherited from parent dir. |
| preview.py → external Greenhouse API (via fetch_all) | Outbound HTTPS with httpx.Timeout(connect=5, read=15); same boundary as Plan 02-01 dispatcher (DSP-03). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-14 | Tampering | User's pending edits clobbered by Plan 02-03 edit | mitigate | Stash-replay protocol (Tasks 2+4): /tmp snapshot → reset to HEAD → apply edit → commit → restore snapshot → re-apply edit on top. Final-state verify confirms both hunks coexist. Plan 01-03 used this exact protocol (commit 2e84994) — proven against this same file. |
| T-02-15 | Tampering | preview.py invoked with hostile args (path traversal, command injection) | mitigate | preview.py uses positional args (data_dir, today, slugs_csv) read via sys.argv. data_dir is os.path.expanduser'd and joined to a fixed-name file (`config.json`). slugs_csv is split on `,` into a list of tokens; tokens are passed as URL slugs to fetch_all (provider modules build URLs via `LIST_URL_TEMPLATE.format(slug=slug)` — no shell, no eval). No untrusted input reaches subprocess shells or interpolated Python. |
| T-02-16 | Information Disclosure | ats_raw/ files leaked via iCloud sync | accept | The user's `<data_dir>` is at `~/Documents/JobSearch` by default — placing it under iCloud is the user's choice. CON-18 (Phase 6) adds the iCloud warning to /scout-setup. Phase 2 inherits the existing 0o700 perms from validate_data.py (Phase 1). |
| T-02-17 | Repudiation | DSP-10 fetch failure silently zeroes companies | mitigate | DSP-05 three-state outcomes are logged to runs.jsonl by preview.py's single append_run call. Phase 5 surfaces "ATS regression suspect" warnings reading from runs.jsonl. |
| T-02-18 | Denial of Service | preview.py multi-fetch_all amplification | mitigate | preview.py contains EXACTLY ONE call to fetch_all() — verified by `grep -c 'fetch_all('` ≤ 2 in Task 1's automated check (the `from ats.dispatcher import fetch_all` import line is the only other match). DSP-03's single-Client contract is preserved at the SKILL boundary; no provider sees N× the expected load. |

</threat_model>

<verification>
After all 4 tasks complete, run this final phase-level smoke:

```bash
# 1. Plan 02-03's commit landed cleanly (one commit covering both files)
git log --oneline | grep -q "feat(02-03):" && \

# 2. preview.py exists, is callable, and has the single-fetch_all invariant
test -f scripts/ats/preview.py && \
test "$(grep -c 'fetch_all(' scripts/ats/preview.py)" -le 2 && \
~/.job-scout-venv/bin/python3 ${PWD}/scripts/ats/preview.py --help | grep -q "ONE process" && \

# 3. The committed scout-run/SKILL.md has Step 2.5 wiring (preview.py + runs_log.append_run + ats_raw)
git show HEAD:skills/scout-run/SKILL.md | grep -q "## Step 2.5: \[ATS-PREVIEW\]" && \
git show HEAD:skills/scout-run/SKILL.md | grep -q "scripts/ats/preview.py" && \
git show HEAD:skills/scout-run/SKILL.md | grep -q "runs_log.append_run" && \
git show HEAD:skills/scout-run/SKILL.md | grep -q "ats_raw" && \

# 4. SKILL.md has ZERO inline fetch_all calls — DSP-03 single-call invariant enforced at SKILL layer
test "$(git show HEAD:skills/scout-run/SKILL.md | grep -c 'fetch_all(')" -eq 0 && \

# 5. User's pending edits are preserved in the working tree (or working tree is clean if HAS_PENDING=0 at session start)
{ git diff --quiet skills/scout-run/SKILL.md && echo "Working tree clean (HAS_PENDING=0 was the case)"; } || \
{ grep -q "## Step 2.5: \[ATS-PREVIEW\]" skills/scout-run/SKILL.md && echo "Plan 02-03 + user pending edits coexist in working tree"; } && \

# 6. /tmp cleanup
test ! -f /tmp/scout-run-SKILL-pre-DSP10.md && \

# 7. Phase 2 final substrate-roundtrip via preview.py (empty-input path — no network)
~/.job-scout-venv/bin/python3 -c "
import sys, json, tempfile, os
sys.path.insert(0, 'scripts')
from ats.preview import run_preview
with tempfile.TemporaryDirectory() as td:
    json.dump({'ats': {}}, open(os.path.join(td, 'config.json'), 'w'))
    open(os.path.join(td, 'runs.jsonl'), 'w').close()
    today = '2026-04-28'
    os.makedirs(os.path.join(td, 'daily', today, 'ats_raw'), exist_ok=True)
    summary = run_preview(td, today, [])
    assert summary['outcome_count'] == 0
    # exactly one runs.jsonl line appended (the daily heartbeat)
    with open(os.path.join(td, 'runs.jsonl')) as f:
        n = sum(1 for L in f if L.strip())
    assert n == 1, f'expected 1 runs.jsonl line, got {n}'
print('PHASE-2 PLAN-03 SMOKE: end-to-end preview.py empty roundtrip OK')
"
```

All seven gates must pass.
</verification>

<success_criteria>
- [ ] scripts/ats/preview.py exists with `run_preview()` + CLI dispatch; ONE fetch_all call (verified by grep -c <= 2 including the import line)
- [ ] preview.py instantiates ZERO httpx.Clients directly — relies on dispatcher.fetch_all to own the Client lifetime per DSP-03
- [ ] preview.py persists raw payloads to `<data_dir>/daily/<TODAY>/ats_raw/<provider>/<slug>.json` for OK_WITH_RESULTS outcomes only (DSP-10 contract)
- [ ] preview.py appends ONE runs.jsonl line per invocation via runs_log.append_run (DSP-07 wiring complete)
- [ ] preview.py prints a JSON summary to stdout with `outcome_count`, `wall_clock_seconds`, `per_provider_outcomes`, `per_company_provider`, `ok_with_results_companies`, `raw_persisted` (the SKILL parses this)
- [ ] skills/scout-run/SKILL.md gains a new `## Step 2.5: [ATS-PREVIEW] Pass 1 (Greenhouse only)` block placed between current Step 2 and Step 3
- [ ] The block invokes `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/preview.py "<data_dir>" "<TODAY>" "<slugs_csv>"` EXACTLY ONCE per /scout-run (no inline fetch_all heredocs)
- [ ] The block does NOT change scoring, tier assignment, or any existing Step 1/2/3/4/5/6/7/8/9 behavior — additive only (DSP-10 locked decision)
- [ ] The user's pending uncommitted edits to skills/scout-run/SKILL.md are PRESERVED at session-end exactly as they were at session-start, verifiable by diff against /tmp snapshot
- [ ] git log shows exactly one new commit: `feat(02-03): ... DSP-10` (covering both new files: preview.py + scout-run/SKILL.md)
- [ ] /tmp/scout-run-SKILL-pre-DSP10.md is cleaned up after Task 4
- [ ] Phase-level smoke (verification block) prints all seven OK lines
- [ ] No new dependencies added (httpx already added in Plan 02-01)
</success_criteria>

<output>
After completion, create `.planning/phases/02-provider-protocol-greenhouse-dispatcher-observability/02-03-wire-preview-SUMMARY.md` with:
- 1-line summary
- Files modified table (scripts/ats/preview.py +N / -0; skills/scout-run/SKILL.md +X / -Y)
- Tasks completed checklist
- Verify results (the 7 OK lines)
- Stash-replay protocol post-mortem (was HAS_PENDING=1 or 0; final-state diff against pre-Task-2 snapshot; confirmation that user's hunks are byte-identical to session-start)
- DSP-03 single-fetch_all invariant verification (grep -c 'fetch_all(' scripts/ats/preview.py output; grep -c 'fetch_all(' on the committed SKILL.md should be 0)
- Phase 2 closeout: all 10 DSP-* requirements landed across the three plans (02-01: DSP-01..08; 02-02: DSP-09; 02-03: DSP-10).
- Hand-off to Phase 3 / phase verifier: dispatcher + Greenhouse provider + runs.jsonl writer + preview.py driver are wired into /scout-run additively. Phase 3 will populate `ats_provider="greenhouse"` for top-30 companies via `/scout-detect`, at which point the [ATS-PREVIEW] block actually exercises real network fetches against real master_targets entries.
</output>

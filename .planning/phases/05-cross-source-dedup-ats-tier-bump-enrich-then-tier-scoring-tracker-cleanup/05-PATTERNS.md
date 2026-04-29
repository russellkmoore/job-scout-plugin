# Phase 5: Cross-source Dedup + ATS Tier Bump + Enrich-then-Tier + Scoring/Tracker Cleanup — Pattern Map

**Mapped:** 2026-04-28
**Files analyzed:** 11 new/modified files
**Analogs found:** 10 / 11

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/ats/dedupe.py` | utility | transform | `scripts/ats/normalize.py` | role-match (same ats/ utility shape, filter-helper + apply_ wrapper pattern) |
| `scripts/tracker_utils.py` | utility | CRUD | `scripts/tracker_utils.py` (self) | exact (surgical in-place modifications) |
| `scripts/ats/runs_log.py` | utility | append-write | `scripts/ats/runs_log.py` (self) | exact (kwarg extension to existing append_run) |
| `scripts/ats/preview.py` | utility | request-response | `scripts/ats/preview.py` (self) | exact (note in research: no changes needed here; routing is in SKILL.md) |
| `skills/scout-run/SKILL.md` | skill | event-driven | `skills/scout-run/SKILL.md` (self) | exact (step-level rewrite of Steps 4.5, 5, 6) |
| `skills/job-scout/references/scoring-rubric.md` | config | — | `skills/job-scout/references/scoring-rubric.md` (self) | exact (single table row replacement) |
| `skills/job-scout/references/search-config.md` | config | — | `skills/job-scout/references/search-config.md` (self) | exact (single bullet replacement) |
| `tests/test_dedup_phase5.py` | test | transform | `tests/test_providers_phase4.py` | role-match (fixture-driven pytest, same PROJECT_ROOT bootstrap) |
| `tests/test_tracker_phase5.py` | test | CRUD | `tests/test_migration.py` | role-match (xlsx round-trip, same tmp_path fixture pattern) |
| `tests/fixtures/linkedin_candidates_sample.json` | fixture | — | `tests/fixtures/ats/greenhouse/airbnb.json` | partial (same JSON fixture shape, different schema) |
| `tests/fixtures/ats_raw_sample/` | fixture | — | `tests/fixtures/ats/` (directory) | partial (same per-provider directory layout) |
| `tests/fixtures/runs_jsonl_history.jsonl` | fixture | — | none (no JSONL fixture exists yet) | no-analog |

---

## Pattern Assignments

### `scripts/ats/dedupe.py` (utility, transform)

**Analog:** `scripts/ats/normalize.py`

**Module docstring pattern** (normalize.py lines 1–14):
```python
"""
dedupe.py — Cross-source dedup for Job Scout Pass 1 (ATS) vs Pass 2/3 (LinkedIn/boards).

Two-key tiered fuzzy dedup using rapidfuzz.token_set_ratio.
DDP-01/02/03/04: scoped per company slug, two-key gate, tiered confidence band,
dedup_decisions output for runs.jsonl.

Usage:
    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/dedupe.py \\
      cross-source \\
      "<data_dir>/daily/<TODAY>/ats_raw/" \\
      "<data_dir>/daily/<TODAY>/linkedin_candidates.json" \\
      "<data_dir>/daily/<TODAY>/dedup_result.json" \\
      --config "<data_dir>/config.json"
"""
```

**2-level sibling bootstrap pattern** (runs_log.py lines 50–52, normalize.py line 14 comment):
```python
# Two-level bootstrap: file → ats → scripts
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from ats.normalize import _normalize_title  # Pitfall 3: import, never copy-paste
```

**ImportError hint pattern — CON-04 compliant** (tracker_utils.py lines 26–37, CONVENTIONS.md note: CON-04 now requires `pipx`/venv, NOT `--break-system-packages`):
```python
try:
    from rapidfuzz import fuzz
except ImportError:
    print(
        "ERROR: rapidfuzz not installed. Install with:\n"
        "  python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate\n"
        "  pip install rapidfuzz\n"
        "  (or: pipx install rapidfuzz)",
        file=sys.stderr,
    )
    sys.exit(1)
```

**Core normalization helpers** (normalize.py lines 102–111 — IMPORT _normalize_title from here, add _loose_key/_tight_key in dedupe.py as new functions per RESEARCH.md Dedup Architecture section):
```python
# In normalize.py (already exists — DO NOT MODIFY):
def _normalize_title(title: str) -> str:
    t = (title or "").casefold()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

# In dedupe.py (new — import _normalize_title first):
def _loose_key(slug: str, title: str) -> str:
    tokens = _normalize_title(title).split()
    return slug + "|" + " ".join(tokens[:3])

def _tight_key(slug: str, title: str) -> str:
    return slug + "|" + _normalize_title(title)
```

**apply_filters wrapper pattern** (normalize.py lines 213–241 — copy the `apply_` prefix convention and config-dict fallback):
```python
def run_cross_source_dedup(
    ats_listings: List[dict],
    linkedin_listings: List[dict],
    config: Optional[dict] = None,
) -> dict:
    """DDP-01/02/03: Two-key tiered dedup. Returns dedup_result dict."""
    cfg = (config or {}).get("dedup", {}).get("thresholds", {})
    auto_merge_threshold = cfg.get("auto_merge", 95)
    review_band_min = cfg.get("review_band_min", 70)
    # ... two-key gate logic
    return {"merged": [...], "review_band": [...], "linkedin_only": [...],
            "ats_only": [...], "decisions": [...]}
```

**CLI subcommand dispatch pattern** (detect.py lines 829–853):
```python
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python3 scripts/ats/dedupe.py <command> [args...]",
            file=sys.stderr,
        )
        print("Commands: cross-source", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "cross-source":
        _cmd_cross_source(sys.argv[2:])
        sys.exit(0)
    elif cmd in ("--help", "-h"):
        print("dedupe.py — Cross-source dedup\nCommands: cross-source")
        sys.exit(0)
    else:
        print(f"ERROR: unknown command {cmd!r}", file=sys.stderr)
        sys.exit(1)
```

**os.path.expanduser at boundary** (tracker_utils.py line 358, state.py line 53):
```python
def _cmd_cross_source(args):
    # expand ~ on all path args before any file I/O
    ats_raw_dir = os.path.expanduser(args[0])
    linkedin_path = os.path.expanduser(args[1])
    output_path = os.path.expanduser(args[2])
    config_path = None
    if "--config" in args:
        config_path = os.path.expanduser(args[args.index("--config") + 1])
```

**JSON as last stdout print** (tracker_utils.py lines 370–373, CONVENTIONS.md logging section):
```python
    # dedup_result.json is written to disk AND printed as last stdout
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(json.dumps({"ok": True, "merged": len(result["merged"]),
                      "review_band": len(result["review_band"]),
                      "decisions": len(result["decisions"])}, indent=2))
```

**Output shape** (RESEARCH.md Dedup Architecture section):
```json
{
  "merged": [...],
  "review_band": [...],
  "linkedin_only": [...],
  "ats_only": [...],
  "decisions": [
    {"action": "auto_merge", "ats_url": "...", "linkedin_url": "...",
     "loose_score": 97, "tight_score": 96, "company_slug": "stripe"},
    {"action": "review_band", ...},
    {"action": "keep_both", ...}
  ]
}
```

---

### `scripts/tracker_utils.py` — CON-13: Split `extract_job_id` (lines 72–77 → two functions)

**Analog:** `scripts/tracker_utils.py` (self — surgical replacement)

**Current function to replace** (lines 72–77):
```python
def extract_job_id(url):
    """Extract numeric LinkedIn job ID from a URL."""
    if not url:
        return None
    match = re.search(r'(\d{10,})', str(url))
    return int(match.group(1)) if match else None
```

**Replacement — two new functions** (RESEARCH.md CON-13 section, verbatim signatures):
```python
def extract_linkedin_job_id(url):
    """Extract numeric LinkedIn job ID — anchored to linkedin.com URLs only.
    Returns int or None. Returns None for non-LinkedIn URLs (career-page,
    ATS board URLs, etc.) so stale-flag and dedup skip non-LinkedIn rows.
    """
    if not url:
        return None
    match = re.search(r'linkedin\.com/jobs/(?:view|search)/\D*(\d{10,})', str(url))
    return int(match.group(1)) if match else None


def extract_dedup_key(url):
    """Return a stable dedup key for any URL. For LinkedIn URLs, returns
    the numeric job ID as a string. For other URLs, returns the URL itself
    (normalized). Used by rebuild() and load_tracker() to deduplicate
    non-LinkedIn rows by full URL rather than ID.
    """
    if not url:
        return None
    linkedin_id = extract_linkedin_job_id(url)
    if linkedin_id is not None:
        return str(linkedin_id)
    return str(url).strip().lower()
```

**Caller migration map** (RESEARCH.md CON-13 table):

| Location | Line | Old call | New call |
|----------|------|----------|----------|
| `load_tracker` | ~146 | `extract_job_id(url)` | `extract_linkedin_job_id(url)` |
| `append_rows` | ~193 | `extract_job_id(url)` | `extract_linkedin_job_id(url)` |
| `is_stale_by_id` | ~82 | `extract_job_id(url)` internally | `extract_linkedin_job_id(url)` |
| `rebuild` | ~277 | `extract_job_id(url)` | `extract_dedup_key(url)` |

Note: `rebuild()`'s `seen_ids` set changes from `set()` of ints to `set()` of strings after CON-13. The dedup logic (`if job_id and job_id in seen_ids`) works identically.

---

### `scripts/tracker_utils.py` — CON-14: Rename `skipped_stale` (lines 188–263)

**Analog:** `scripts/tracker_utils.py` (self — local variable rename only)

**Critical constraint (Pitfall 6):** The returned dict key at line 263 ALREADY uses `"flagged_stale"` — it must NOT change. Only the LOCAL variable `skipped_stale` is renamed.

**Exact surgery** (RESEARCH.md CON-14 section):
```python
# Line 188 — BEFORE:
skipped_stale = 0
# Line 188 — AFTER:
flagged_stale_count = 0

# Line 204 — BEFORE:
skipped_stale += 1
# Line 204 — AFTER:
flagged_stale_count += 1

# Line 206 — REMOVE this comment entirely:
# Still add it, but flagged — user can decide

# Line 263 — BEFORE (returned dict — DO NOT CHANGE THE KEY):
"flagged_stale": skipped_stale,
# Line 263 — AFTER:
"flagged_stale": flagged_stale_count,
```

---

### `scripts/tracker_utils.py` — CON-20: User-column preservation in `load_tracker` + `_write_tracker`

**Analog:** `scripts/tracker_utils.py` (self) + `scripts/validate_data.py` (never-drop-user-columns convention)

**Root cause** (RESEARCH.md CON-20 section, Pitfall 2):
- `load_tracker` (line 139–148): already reads all columns via `values_only=True` into `row_list` — extra-wide rows survive in memory.
- `_write_tracker` (lines 323–325): `break` at `col > len(HEADERS)` drops user-added data silently.
- `load_tracker` starts at `min_row=2` (line 139) — never reads the header row — so user-added header NAMES are lost.

**Fix pattern — `load_tracker` additions** (after line 137, before iter_rows loop):
```python
# Discover user-added header names from row 1 for passthrough
ws_headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
user_extra_headers = ws_headers[len(HEADERS):]  # may be empty list
```

**Fix pattern — `_write_tracker` replacement of break guard** (lines 323–325):
```python
# BEFORE:
for col, val in enumerate(row, 1):
    if col > len(HEADERS):
        break
    cell = ws.cell(row=r_idx, column=col, value=val)
    ...

# AFTER — replace break with write-through:
for col, val in enumerate(row, 1):
    cell = ws.cell(row=r_idx, column=col, value=val)
    cell.fill = row_fill
    cell.border = THIN_BORDER
    cell.alignment = Alignment(wrap_text=True, vertical='top')
    if col > len(HEADERS):
        # User-added column: plain passthrough — no special formatting
        continue
    # existing per-column formatting (score center, tier bold, hyperlink) follows
    if col == 6:
        ...
```

**Fix pattern — re-emit user headers in `_write_tracker`** (after the standard HEADERS loop, around line 311):
```python
# Re-emit user-added column headers (if any were discovered in load_tracker)
# user_extra_headers must be threaded from load_tracker to _write_tracker
for i, extra_header in enumerate(user_extra_headers, len(HEADERS) + 1):
    cell = ws.cell(row=1, column=i, value=extra_header)
    cell.fill = HEADER_FILL
    cell.font = HEADER_FONT
    cell.alignment = Alignment(horizontal='center', wrap_text=True)
    cell.border = THIN_BORDER
```

**Signature threading note:** `user_extra_headers` must be returned from `load_tracker` and passed to `_write_tracker`. The cleanest approach that avoids breaking the 3-tuple return of `load_tracker` is to return a 4-tuple: `(wb, rows, job_ids, user_extra_headers)`. All callers (`append_rows`, `rebuild`, `get_dedup_set`) must be updated to unpack 4 values. `_write_tracker` gains a new `user_extra_headers: list = None` parameter (defaults to `[]`).

---

### `scripts/ats/runs_log.py` — D-2: Extend `append_run()` with new kwargs

**Analog:** `scripts/ats/runs_log.py` (self — kwarg extension)

**Current signature** (runs_log.py lines 90–97):
```python
def append_run(
    runs_log_path: str,
    wall_clock_seconds: float,
    per_provider_outcomes: Dict[str, Dict[str, int]],
    per_company_provider: Dict[str, Dict[str, Any]],
    per_provider_listings: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
```

**New signature with Phase 5 kwargs** (VALIDATION.md D-2, RESEARCH.md Open Question 4 resolution):
```python
def append_run(
    runs_log_path: str,
    wall_clock_seconds: float,
    per_provider_outcomes: Dict[str, Dict[str, int]],
    per_company_provider: Dict[str, Dict[str, Any]],
    per_provider_listings: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    timestamp: Optional[str] = None,
    # Phase 5 additions (D-2) — all Optional, non-breaking
    dedup_decisions: Optional[List[Dict[str, Any]]] = None,
    regression_suspects: Optional[List[Dict[str, Any]]] = None,
    pass2_board_status: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
```

**Line dict extension** (runs_log.py lines 130–135 — append to the line dict before writing):
```python
line = {
    "timestamp": timestamp,
    "wall_clock_seconds": round(float(wall_clock_seconds), 3),
    "providers": providers_block,
    "per_company_provider": per_company_provider,
}
# Phase 5 optional telemetry (D-2) — only emitted if non-None/non-empty
if dedup_decisions:
    line["dedup_decisions"] = dedup_decisions
if regression_suspects:
    line["regression_suspects"] = regression_suspects
if pass2_board_status:
    line["pass2_board_status"] = pass2_board_status
```

**CLI stats.json passthrough** (runs_log.py lines 163–170 — extend to pass new kwargs):
```python
line = append_run(
    runs_log_path=runs_log_path,
    wall_clock_seconds=stats["wall_clock_seconds"],
    per_provider_outcomes=stats["per_provider_outcomes"],
    per_company_provider=stats["per_company_provider"],
    per_provider_listings=stats.get("per_provider_listings"),
    timestamp=stats.get("timestamp"),
    # Phase 5 passthrough
    dedup_decisions=stats.get("dedup_decisions"),
    regression_suspects=stats.get("regression_suspects"),
    pass2_board_status=stats.get("pass2_board_status"),
)
```

**New `regression-suspects` subcommand** (detect.py CLI dispatch pattern, lines 829–853):
```python
elif cmd == "regression-suspects":
    _cmd_regression_suspects(sys.argv[2:])
    sys.exit(0)

def _cmd_regression_suspects(args):
    """regression-suspects <runs_log_path> [--lookback 5]

    Reads the last N+1 lines of runs.jsonl (N prior + 1 current).
    Prints JSON list of {company_slug, provider, prior_ok_count} for
    any (company, provider) that was OK_WITH_RESULTS >= lookback/2
    in the prior N runs but is OK_ZERO or ERROR in the current run.

    Pitfall 5: reads lines [-lookback-1:-1] for prior, [-1] for current.
    """
    runs_log_path = os.path.expanduser(args[0])
    lookback = 5
    if "--lookback" in args:
        lookback = int(args[args.index("--lookback") + 1])

    with open(runs_log_path, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f.readlines()[-(lookback + 1):]]

    if len(lines) < 2:
        print(json.dumps([]))
        return

    current = lines[-1]
    prior = lines[-(lookback + 1):-1]  # Pitfall 5: last N prior, NOT including current
    # ... comparison logic
    print(json.dumps(suspects, indent=2))  # JSON as last stdout
```

---

### `skills/scout-run/SKILL.md` — Step 2.5, 4.5, 5, 6 rewrite

**Analog:** `skills/scout-run/SKILL.md` (self)

**Step 2.5 JSON-LD routing addition** (after existing 5-provider filter block at line 159, Pitfall 4 — use `career_page_url` NOT `careers_url`):
```markdown
   **JSON-LD routing (Phase 5 — closes Phase 4 deferral):** After building the
   5-provider targets above, add a SECOND block for JSON-LD candidates:
   For any row where `ats_provider == "none"` AND `career_page_url` is non-empty,
   append `<career_page_url>|jsonld` to `<targets_csv>`.
   Note: the column is `career_page_url` (col 3 in master_targets.csv) —
   there is no `careers_url` column.
```

**New Step 4.5 — Cross-source dedup** (insert between current Step 4 and Step 5):
```markdown
## Step 4.5: Cross-source dedup

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/dedupe.py \
  cross-source \
  "<data_dir>/daily/<TODAY>/ats_raw/" \
  "<data_dir>/daily/<TODAY>/linkedin_candidates.json" \
  "<data_dir>/daily/<TODAY>/dedup_result.json" \
  --config "<data_dir>/config.json"
```

Read `dedup_result.json`. The merged set becomes the unified candidate set for Step 5.
Any listings in `review_band[]` should be logged to `ats_detection_review.csv` for the user.
```

**Step 5 rewrite — enrich-then-tier order** (replace current Step 5 at line 241, per D-1):
```markdown
## Step 5: Enrich-then-Tier (D-1: enrich BEFORE final scoring)

**Enrichment scope (D-1 locked):** Enrich any ATS-sourced listing whose base score
(5-category rubric, no bump) would reach B-tier OR ABOVE — i.e., any listing that
could become A-tier after the +1 ATS bump. Do NOT wait until after tier assignment
to decide what to enrich.

(a) **For every ATS-sourced listing in the enrich scope** (source=ats:*):
    Navigate to `https://www.linkedin.com/company/<linkedin_slug>/people/`.
    Derive <linkedin_slug> from company_name: lowercase + replace spaces with dashes
    + strip common suffixes (", Inc.", ", LLC", " Corp"). (D-3 — no schema column needed)
    Capture: shared-connection count + top 3 named connections.
    If page redirects / login wall: log `linkedin_enrich_unavailable` in the run stats,
    continue — enrichment is non-blocking.

    **Rate-limit rule (CON-11):** After every 5th LinkedIn navigation in this loop,
    pause 10–15 seconds before the next. The counter does NOT reset between companies.

(b) **Apply scoring rubric** with enriched connection data in hand.
    Apply +1 tier bump: any listing where source=ats:* AND posted_date ≤ 30 days ago
    gets +1 tier elevation (B→A, C→B; A stays A). See scoring-rubric.md for the
    exact rule replacing the dead pipeline_tier +5 row.

(c) **Assign final tier** using post-enrichment, post-bump score.
    Hard cap: 10 A-tier per run (existing rule unchanged).
```

**Step 6 Honest notes additions** (after existing Honest notes block, per DDP-08/CON-15, Pitfall 5):
```markdown
### ATS regression suspects (DDP-08)
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/runs_log.py regression-suspects \
  "<data_dir>/runs.jsonl" --lookback 5
```
For any suspect returned, surface: "**ATS regression suspect:** <company> / <provider> —
returned OK_WITH_RESULTS in <N>/5 prior runs but OK_ZERO/ERROR today."

### Pass-2 board-broken warnings (CON-15)
From `pass2_board_status` in the last 5 runs.jsonl lines, flag any board
that returned 0 results in ≥3/5 runs: "**Board appears broken:** <board_name>
returned 0 results in <N>/5 recent runs."
```

**Bash blocks must be verbatim-runnable** (CONVENTIONS.md Markdown Style section):
All new bash blocks use `${CLAUDE_PLUGIN_ROOT}` and `<data_dir>` placeholders consistent with existing SKILL.md blocks.

---

### `skills/job-scout/references/scoring-rubric.md` — CON-10 + DDP-05

**Analog:** `skills/job-scout/references/scoring-rubric.md` (self — single table row replacement)

**Line 111 — current dead row to replace** (RESEARCH.md CON-10, VERIFIED):
```
| Company on Target Pipeline | +5 | Company exists in master_targets.csv with pipeline_tier 1-3 |
```

**Replacement row** (RESEARCH.md CON-10 + DDP-05):
```
| ATS warm path | +1 tier | source=ats:* AND posted_date ≤ 30 days (ISO date comparison against today's date) |
```

Note: "+1 tier" = tier elevation (B→A, C→B, A stays A), NOT a score point addition. The rubric text must be unambiguous about this distinction.

---

### `skills/job-scout/references/search-config.md` — CON-09

**Analog:** `skills/job-scout/references/search-config.md` (self — single bullet replacement)

**Line 52 — current dead bullet to replace** (RESEARCH.md CON-09, VERIFIED):
```
2. Companies on the user's pipeline list (`pipeline_tier <= 2`).
```

**Replacement bullet** (RESEARCH.md CON-09):
```
2. Companies with `linkedin_connection_count` ≥ 1 AND `ats_provider` populated (ATS + warm path).
```

Full replacement list context (lines 50–54 post-fix):
```
1. Companies with 3+ named connections (warm path likely).
2. Companies with linkedin_connection_count ≥ 1 AND ats_provider populated (ATS + warm path).
3. Companies in industries_preferred from config.
4. Companies with any detected ATS provider (richer data).
```

---

### `tests/test_dedup_phase5.py` (test, transform)

**Analog:** `tests/test_providers_phase4.py`

**File header + bootstrap pattern** (test_providers_phase4.py lines 1–27):
```python
"""test_dedup_phase5.py -- Wave 0 RED tests for DDP-01..08, CON-10/11/15.

All tests are expected to FAIL until Wave 1 (dedupe.py) lands. Run with:

    ~/.job-scout-venv/bin/python3 -m pytest tests/test_dedup_phase5.py -x -q
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

LINKEDIN_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "linkedin_candidates_sample.json"
ATS_RAW_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "ats_raw_sample"
RUNS_JSONL_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "runs_jsonl_history.jsonl"
```

**Fixture-based test structure** (test_providers_phase4.py lines 33–90 pattern):
```python
def test_cross_source_match():
    """DDP-01: dedupe.py cross-source matches ATS vs LinkedIn by slug + title."""
    from ats import dedupe
    ats_listings = json.loads((ATS_RAW_FIXTURE_DIR / "auto_merge_ats.json").read_text())
    linkedin_listings = json.loads(LINKEDIN_FIXTURE.read_text())
    result = dedupe.run_cross_source_dedup(ats_listings, linkedin_listings)
    assert len(result["merged"]) >= 1
    assert result["decisions"][0]["action"] == "auto_merge"
```

**Mock pattern for httpx** (test_providers_phase4.py lines 72–90 — adapt for any I/O-less unit tests):
```python
from unittest.mock import MagicMock
mock_sem = MagicMock()
mock_sem.__enter__ = MagicMock(return_value=None)
mock_sem.__exit__ = MagicMock(return_value=False)
```

**Regression-suspect test pattern** (uses RUNS_JSONL_FIXTURE, Pitfall 5 — must verify [-6:-1] offset):
```python
def test_regression_suspect():
    """DDP-08: company with OK_WITH_RESULTS >= 3/5 prior but OK_ZERO today is flagged."""
    from ats.runs_log import _find_regression_suspects  # or call CLI
    lines = [json.loads(l) for l in RUNS_JSONL_FIXTURE.read_text().splitlines()]
    suspects = _find_regression_suspects(lines, lookback=5)
    assert any(s["company_slug"] == "acme" for s in suspects)
```

---

### `tests/test_tracker_phase5.py` (test, CRUD)

**Analog:** `tests/test_migration.py`

**File header + tmp_path pattern** (test_migration.py lines 1–53):
```python
"""test_tracker_phase5.py -- Wave 0 RED tests for CON-12, CON-13, CON-15, CON-20.

Run with:
    ~/.job-scout-venv/bin/python3 -m pytest tests/test_tracker_phase5.py -x -q
"""
import sys
import json
from pathlib import Path

import openpyxl
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
```

**Round-trip fixture pattern** (test_migration.py lines 45–53 — use tmp_path, not real files):
```python
@pytest.fixture
def tracker_with_user_col(tmp_path):
    """Create a tracker xlsx with a user-added 'My Notes' column in column 17."""
    import openpyxl
    from tracker_utils import create_empty_tracker, HEADERS
    path = tmp_path / "JobScout_Tracker.xlsx"
    create_empty_tracker(str(path))
    wb = openpyxl.load_workbook(str(path))
    ws = wb.active
    ws.cell(row=1, column=len(HEADERS) + 1, value="My Notes")
    ws.cell(row=2, column=len(HEADERS) + 1, value="Important lead")
    wb.save(str(path))
    return path
```

**User-column preservation test** (CON-20 — tests the exact failure mode from Pitfall 2):
```python
def test_user_column_preservation(tracker_with_user_col, tmp_path):
    """CON-20: User-added xlsx column survives append_rows round-trip."""
    from tracker_utils import append_rows
    new_rows_path = tmp_path / "new_rows.json"
    new_rows_path.write_text(json.dumps([{
        "date_found": "2026-04-28", "job_title": "VP Eng", "company": "Acme",
        "location": "Remote", "job_url": "https://linkedin.com/jobs/view/1234567890123",
        "tier": "A", "score": 80, "status": "New",
    }]))
    append_rows(str(tracker_with_user_col), str(new_rows_path))
    wb = openpyxl.load_workbook(str(tracker_with_user_col))
    ws = wb.active
    from tracker_utils import HEADERS
    assert ws.cell(row=1, column=len(HEADERS) + 1).value == "My Notes"
    assert ws.cell(row=2, column=len(HEADERS) + 1).value == "Important lead"
```

**extract_linkedin_job_id tests** (CON-13 — three URL types to assert):
```python
def test_extract_linkedin_job_id():
    """CON-13: extract_linkedin_job_id returns None for non-LinkedIn URLs."""
    from tracker_utils import extract_linkedin_job_id
    assert extract_linkedin_job_id("https://linkedin.com/jobs/view/1234567890123") == 1234567890123
    assert extract_linkedin_job_id("https://boards.greenhouse.io/airbnb/jobs/7890") is None
    assert extract_linkedin_job_id("https://jobs.lever.co/stripe/abc-123") is None
    assert extract_linkedin_job_id(None) is None

def test_extract_dedup_key():
    """CON-13: extract_dedup_key returns URL for non-LinkedIn rows."""
    from tracker_utils import extract_dedup_key
    assert extract_dedup_key("https://boards.greenhouse.io/airbnb/jobs/7890") == \
        "https://boards.greenhouse.io/airbnb/jobs/7890"
    assert extract_dedup_key("https://linkedin.com/jobs/view/1234567890123") == "1234567890123"
```

---

### `tests/fixtures/linkedin_candidates_sample.json`

**Analog:** `tests/fixtures/ats/greenhouse/airbnb.json` (shape convention)

**Shape:** Array of 3 Listing dicts (as produced by `Listing.to_dict()`). Must include:
- 1 pair that auto-merges with an entry in `ats_raw_sample/` (loose ≥95 + tight ≥95)
- 1 pair that falls in review band (loose 70–94 OR tight 70–94)
- 1 listing with no ATS match (keep_both, score <70)

All entries must have `source="linkedin"` and realistic `posted_date` (within 30 days for tier-bump test coverage).

**SOURCE.md provenance** (tests/fixtures/ats/greenhouse/ has a SOURCE.md — create one in fixtures/ root):
Each fixture should document what it represents and why values were chosen.

---

### `tests/fixtures/ats_raw_sample/`

**Analog:** `tests/fixtures/ats/` (directory layout)

**Structure** (matching preview.py's raw persistence layout at lines 157–170):
```
tests/fixtures/ats_raw_sample/
  greenhouse/
    acme.json        # auto-merge pair counterpart for linkedin_candidates_sample.json[0]
  lever/
    example.json     # review-band pair counterpart for linkedin_candidates_sample.json[1]
```

Each file shape matches the `payload` dict written by preview.py (lines 160–169):
```json
{
  "company_slug": "acme",
  "provider": "greenhouse",
  "http_status": 200,
  "elapsed_seconds": 0.42,
  "raw": {},
  "listings": [{ ...Listing.to_dict() output... }]
}
```

---

## Shared Patterns

### Sibling-script bootstrap (2-level, for scripts/ats/*.py)

**Source:** `scripts/ats/runs_log.py` lines 50–52
**Apply to:** `scripts/ats/dedupe.py`
```python
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
```

### CON-04-compliant ImportError hint (pipx/venv, NOT --break-system-packages)

**Source:** `scripts/tracker_utils.py` lines 26–37 (pattern), updated per CONVENTIONS.md CON-04 note
**Apply to:** `scripts/ats/dedupe.py` (for `rapidfuzz` import)
```python
try:
    from rapidfuzz import fuzz
except ImportError:
    print(
        "ERROR: rapidfuzz not installed. Install with:\n"
        "  python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate\n"
        "  pip install rapidfuzz\n"
        "  (or: pipx install rapidfuzz)",
        file=sys.stderr,
    )
    sys.exit(1)
```

### JSON as last stdout + human-readable before it

**Source:** `scripts/tracker_utils.py` lines 370–373; CONVENTIONS.md logging section
**Apply to:** `scripts/ats/dedupe.py` CLI, `scripts/ats/runs_log.py` regression-suspects subcommand
```python
# Human-readable progress lines to stdout first
print(f"Processed {len(decisions)} dedup decisions across {n_companies} companies")
# Machine-consumable JSON is the LAST print
print(json.dumps(result, indent=2))
```

### os.path.expanduser at CLI boundary

**Source:** `scripts/tracker_utils.py` line 358; `scripts/state.py` line 53
**Apply to:** `scripts/ats/dedupe.py` `_cmd_cross_source`, `scripts/ats/runs_log.py` `_cmd_regression_suspects`
```python
path = os.path.expanduser(sys.argv[2])
```

### Module-level docstring with Usage block

**Source:** `scripts/ats/runs_log.py` lines 1–38; `scripts/state.py` lines 1–18
**Apply to:** `scripts/ats/dedupe.py`
Every new Python module opens with: module name + one-sentence purpose + Usage: block with verbatim CLI example.

### pytest PROJECT_ROOT bootstrap

**Source:** `tests/test_providers_phase4.py` lines 16–18; `tests/test_migration.py` lines 35–37
**Apply to:** `tests/test_dedup_phase5.py`, `tests/test_tracker_phase5.py`
```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
```

### `(ok, message)` return tuples from validators

**Source:** `scripts/validate_data.py` pattern; CONVENTIONS.md error handling section
**Apply to:** Any new helper function in `dedupe.py` that validates config keys

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/fixtures/runs_jsonl_history.jsonl` | fixture | — | No JSONL fixture exists in `tests/fixtures/` yet; must be hand-crafted with 6+ lines following the `runs_log.py` schema (timestamp, wall_clock_seconds, providers, per_company_provider). Include at least one `(company, provider)` pair with OK_WITH_RESULTS in lines 1–5 and OK_ZERO in line 6 to make the regression-suspect test deterministic. |

---

## Critical Pitfall Index (for planner reference)

| Pitfall | File | Guard |
|---------|------|-------|
| **P1** Enrich-then-tier ordering | SKILL.md Step 5 | Enrich any ATS listing reaching B-tier or above (base score), BEFORE final scoring. D-1 is locked. |
| **P2** `_write_tracker` break drops user cols | `tracker_utils.py` `_write_tracker` | Replace `break` with write-through; thread `user_extra_headers` as 4th return value from `load_tracker`. |
| **P3** `_normalize_title` shared with Phase 4 | `dedupe.py` | IMPORT from `normalize.py`, never copy-paste. If Phase 5 needs different normalization, add a new function in `dedupe.py`. |
| **P4** `careers_url` column doesn't exist | SKILL.md Step 2.5 | Use `career_page_url` (col 3, verified in schema.py). The word `careers_url` must not appear in any Phase 5 code or docs. |
| **P5** Regression-suspect reads wrong offset | `runs_log.py` regression-suspects | Read `lines[-(lookback+1):-1]` for prior, `lines[-1]` for current. The current run IS already appended. |
| **P6** `skipped_stale` rename vs dict key | `tracker_utils.py` | Rename LOCAL VARIABLE only. Dict key `"flagged_stale"` at line 263 stays unchanged or SKILL Step 7 breaks. |

---

## Metadata

**Analog search scope:** `scripts/`, `scripts/ats/`, `tests/`, `skills/scout-run/`, `skills/job-scout/references/`
**Files scanned:** 11 source files read in full; 3 files partially sampled via targeted Grep + offset reads
**Pattern extraction date:** 2026-04-28

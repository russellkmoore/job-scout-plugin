# Phase 3: Detection + `/scout-detect` skill + lazy inline detect + dead-doc-ref cleanup — Pattern Map

**Mapped:** 2026-04-29
**Files analyzed:** 8 new/modified files
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scripts/ats/detect.py` | utility/CLI | request-response + batch | `scripts/ats/dispatcher.py` (concurrency shape) + `scripts/state.py` (CLI dispatch) | role-match (detection vs fetch, same structural pattern) |
| `skills/scout-detect/SKILL.md` | skill | request-response | `skills/scout-setup/SKILL.md` (multi-step orchestration) | role-match |
| `tests/test_detection.py` | test | batch | `tests/test_migration.py` (fixture-driven pytest, project-root bootstrap) | exact |
| `tests/conftest.py` | test config | — | `tests/test_migration.py` (same directory, same bootstrap pattern) | partial (conftest doesn't exist yet; pattern from test_migration.py) |
| `skills/scout-run/SKILL.md` | skill (modify) | request-response | existing `skills/scout-run/SKILL.md` Step 2.5 `[ATS-PREVIEW]` block (lines 110–157) | exact (add Step 2b before this block) |
| `skills/job-scout/references/file-contract.md` | doc (modify) | — | existing file-contract.md Persistent files table (lines 28–38) | exact (add row to existing table) |
| `skills/job-scout/SKILL.md` | doc (modify) | — | existing `skills/job-scout/SKILL.md` lines 46, 105 (dead references) | exact (3-line string replacements) |
| `skills/job-scout/references/search-config.md` | doc (modify) | — | existing `search-config.md` line 28 (dead reference) | exact (1-line string replacement) |

---

## Pattern Assignments

### `scripts/ats/detect.py` (utility/CLI, request-response + batch)

**Primary analog:** `scripts/ats/dispatcher.py` (concurrency + httpx pattern)
**Secondary analog:** `scripts/state.py` (CLI dispatch pattern)

---

**Module docstring pattern** (from `scripts/ats/dispatcher.py` lines 1–26 and `scripts/state.py` lines 1–18):
```python
#!/usr/bin/env python3
"""
detect.py — ATS provider detection CLI for Job Scout.

Exposes two subcommands:
  detect-one <company_slug> [--name <display_name>] [--data-dir <data_dir>]
  detect-batch <csv_path> [--limit N] [--force] [--data-dir <data_dir>]

detect-one probes each provider in PROVIDERS registry order, applies the
two-factor gate (HTTP 200 + ≥1 job + rapidfuzz name match ≥85%), and prints
a JSON result. detect-batch reads master_targets.csv, runs detect-one logic
for each qualifying row concurrently, writes back to CSV on the main thread,
and appends a telemetry line to runs.jsonl.

Usage:
    python3 scripts/ats/detect.py detect-one airbnb --name "Airbnb, Inc." --data-dir <data_dir>
    python3 scripts/ats/detect.py detect-batch <data_dir>/master_targets.csv --limit 30 --data-dir <data_dir>
"""
```

---

**Imports + sibling-script bootstrap pattern** (from `scripts/ats/dispatcher.py` lines 28–57):

Note: `detect.py` lives at `scripts/ats/detect.py`, so it uses the 2-level bootstrap (same as `dispatcher.py`):

```python
import csv
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

try:
    import httpx
except ImportError:
    print(
        "ERROR: httpx not installed. Install with: "
        "python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate && pip install 'httpx>=0.27,<0.29'"
        "  (or: pip install --user 'httpx>=0.27,<0.29').",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from rapidfuzz import fuzz
except ImportError:
    print(
        "ERROR: rapidfuzz not installed. Install with: "
        "python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate && pip install rapidfuzz"
        "  (or: pip install --user rapidfuzz).",
        file=sys.stderr,
    )
    sys.exit(1)

# Sibling-script bootstrap (2-level — file → ats → scripts).
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from ats import PROVIDERS                                    # noqa: E402
from ats.providers.base import DetectionResult, DetectionStatus  # noqa: E402
from ats.dispatcher import load_caps_and_kill_switch, DEFAULT_PROVIDER_CAPS, DEFAULT_TIMEOUT, DEFAULT_USER_AGENT  # noqa: E402
from ats.runs_log import append_run                          # noqa: E402
```

---

**CLI dispatch pattern** (from `scripts/state.py` lines 106–136 and `scripts/ats/dispatcher.py` lines 383–416):

```python
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python3 scripts/ats/detect.py <detect-one|detect-batch> [args...]",
            file=sys.stderr,
        )
        print("Subcommands: detect-one, detect-batch", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "detect-one":
        _cmd_detect_one(sys.argv[2:])
    elif cmd == "detect-batch":
        _cmd_detect_batch(sys.argv[2:])
    elif cmd in ("--help", "-h"):
        print("detect.py — ATS provider detection\nSubcommands: detect-one, detect-batch")
    elif cmd == "--version":
        print("detect.py: Phase 3 DET-01..07, v0.4")
    else:
        print(f"ERROR: unknown command {cmd!r}", file=sys.stderr)
        sys.exit(1)
```

---

**Error/exception pattern for unrecoverable conditions** (from `scripts/ats/dispatcher.py` lines 250–271):

```python
except (KeyboardInterrupt, MemoryError, SystemExit):
    raise  # Tier 1: re-raise unrecoverable signals
except Exception as exc:  # noqa: BLE001
    elapsed = time.monotonic() - t0
    err = f"{type(exc).__name__}: {exc}"
    print(f"ERROR: {provider_name}/{company_slug}: {err}", file=sys.stderr)
    return DetectionResult(
        provider="",
        status=DetectionStatus.ERROR,
        board_url=None,
        confidence=0.0,
        evidence={"error": err, "elapsed_seconds": round(elapsed, 3)},
    )
```

---

**Semaphore + ThreadPoolExecutor pattern** (from `scripts/ats/dispatcher.py` lines 143–179 and 315–342):

```python
# detect.py creates its OWN semaphores (not sharing dispatcher._SEMAPHORES)
# to avoid detect-batch + scout-run cross-starvation (A1 in RESEARCH.md).
_DET_SEMAPHORES: Dict[str, threading.Semaphore] = {}
_DET_SEMAPHORE_LOCK = threading.Lock()

def _init_detect_semaphores(caps: Dict[str, int]) -> None:
    with _DET_SEMAPHORE_LOCK:
        _DET_SEMAPHORES.clear()
        _DET_SEMAPHORES.update({p: threading.Semaphore(n) for p, n in caps.items()})

# ThreadPoolExecutor + futures pattern (detect-batch):
with ThreadPoolExecutor(max_workers=max_workers) as pool:
    futures = [
        pool.submit(_detect_one_company, slug, name, client)
        for slug, name in detect_tasks
    ]
    results: List[DetectionResult] = []
    for fut in futures:
        results.append(fut.result())
# Write-back to CSV happens AFTER this block, on the main thread.
```

---

**httpx.Client instantiation pattern** (from `scripts/ats/dispatcher.py` lines 315–325):

```python
client = httpx.Client(
    timeout=DEFAULT_TIMEOUT,
    headers={"User-Agent": DEFAULT_USER_AGENT},
    limits=httpx.Limits(
        max_connections=max_workers, max_keepalive_connections=max_workers
    ),
    follow_redirects=True,
)
# Always close in finally:
try:
    ...
finally:
    client.close()
```

---

**load_caps_and_kill_switch pattern** (from `scripts/ats/dispatcher.py` lines 110–140):

`detect.py` calls the SAME `load_caps_and_kill_switch(config_path)` from `dispatcher.py`. The function already handles missing config, JSONDecodeError, and per-key validation. Reuse via import — do not duplicate.

---

**JSON final-print pattern** (from `scripts/validate_data.py:141` convention and `scripts/ats/dispatcher.py` lines 404–415):

The LAST `print()` of `detect-one` and `detect-batch` must be a JSON dict (the machine-readable output the SKILL captures):

```python
# detect-one final print:
print(json.dumps({
    "company_slug": company_slug,
    "company_name": company_name,
    "provider": result.provider,
    "status": result.status.value,
    "board_url": result.board_url,
    "confidence": round(result.confidence, 4),
    "name_match_score": result.evidence.get("name_match_score", 0.0),
    "evidence": result.evidence,
}, indent=2))
sys.exit(0)

# detect-batch final print:
print(json.dumps({
    "total": len(detect_tasks),
    "confirmed": confirmed_count,
    "borderline": borderline_count,
    "not_found": not_found_count,
    "error": error_count,
    "skipped": skipped_count,
    "wall_clock_seconds": round(wall_clock, 3),
    "companies": per_company_results,
}, indent=2))
sys.exit(0)
```

---

**CSV write-back pattern** (derived from `scripts/validate_data.py` user-column preservation rule + RESEARCH.md Pattern 4):

```python
def _write_back(csv_path: str, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    """Write updated rows to master_targets.csv preserving column order.

    fieldnames must be derived from the EXISTING CSV header (read before
    any modification) so user-added columns are preserved at the end.
    Never derive fieldnames from MASTER_TARGETS_COLUMNS alone.
    """
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
```

---

**Append-only CSV pattern** (from `scripts/ats/runs_log.py` lines 137–141):

```python
# For ats_detection_review.csv — same open-in-'a'-mode, write-header-once pattern:
def _append_borderline(review_path: str, row: Dict[str, Any]) -> None:
    file_exists = os.path.isfile(review_path)
    with open(review_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "detected_date", "company_name", "company_slug", "provider",
            "name_match_score", "ats_board_url", "returned_company_name", "action",
        ])
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
        f.flush()
```

---

**Idempotency skip pattern** (from RESEARCH.md Pattern 3 — concrete implementation):

```python
def _should_skip(row: Dict[str, Any], force: bool) -> Tuple[bool, str]:
    """Returns (skip_bool, reason_string). manual lock is absolute."""
    ats_prov = (row.get("ats_provider") or "").strip()
    if ats_prov == "manual":
        return True, "manual-lock"
    if ats_prov and not force:
        last_hit = (row.get("last_ats_hit_date") or "").strip()
        if last_hit:
            try:
                delta = (date.today() - date.fromisoformat(last_hit)).days
                if delta < 30:
                    return True, f"fresh-detection:{delta}d-ago"
            except ValueError:
                pass
        return True, f"already-set:{ats_prov}"
    return False, ""
```

---

**`append_run` call pattern for detection telemetry** (from `scripts/ats/runs_log.py` lines 90–143):

`detect-batch` calls `append_run` with a detection-specific `per_company_provider` structure. The existing `append_run` signature accepts arbitrary `per_company_provider` dicts — use it directly with a `run_type` key injected into the line via the `per_company_provider` dict:

```python
# Workaround: runs_log.append_run does not yet support run_type.
# Write the detection telemetry line using the same open-append-flush
# pattern directly (until append_run gains an extra_fields param):
detection_line = {
    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "run_type": "detect_batch",
    "wall_clock_seconds": round(wall_clock, 3),
    "companies_total": len(detect_tasks),
    "confirmed": confirmed_count,
    "borderline": borderline_count,
    "not_found": not_found_count,
    "error": error_count,
    "skipped": skipped_count,
    "per_company": per_company_results,
}
with open(runs_log_path, "a", encoding="utf-8") as f:
    f.write(json.dumps(detection_line, ensure_ascii=False, separators=(",", ":")) + "\n")
    f.flush()
```

---

### `skills/scout-detect/SKILL.md` (skill, request-response)

**Analog:** `skills/scout-setup/SKILL.md` (multi-step sequential orchestration skill)

---

**Frontmatter pattern** (from `skills/scout-setup/SKILL.md` lines 1–6 and `skills/scout-run/SKILL.md` lines 1–6):

```yaml
---
name: scout-detect
description: Detect ATS providers for top-connection companies and populate ats_provider + ats_board_url in master_targets.csv. Triggers when the user types `/scout-detect` or asks to "detect job boards", "find which ATS my target companies use", "populate ATS fields".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, TodoWrite
version: 0.4.0
---
```

---

**Pre-read block pattern** (from `skills/scout-setup/SKILL.md` lines 10–13 and `skills/scout-run/SKILL.md` lines 13–17):

```markdown
Read these before starting:
- `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/SKILL.md` (core skill knowledge)
- `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/file-contract.md` (where every file lives)
```

---

**Step N: Resolve data_dir pattern** (from `skills/scout-run/SKILL.md` lines 23–34):

```markdown
## Step 1: Resolve `data_dir` and validate

1. **Resolve `data_dir`:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state.py resolve
   ```
   - Exit code 0 → use the printed path as `<data_dir>`.
   - Exit code 2 → tell the user "No Job Scout state found. Run `/scout-setup` first." Stop.

2. **Validate and auto-migrate the data directory:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_data.py "<data_dir>"
   ```
   If it exits non-zero, surface the message and stop.
```

---

**Bash block verbatim-runnable pattern** (from `skills/scout-run/SKILL.md` lines 129–130 — the ONE Bash call constraint):

```markdown
## Step N: Run batch detection

Call `detect-batch` with ONE Bash invocation:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/detect.py detect-batch \
  "<data_dir>/master_targets.csv" \
  --limit 30 \
  --data-dir "<data_dir>"
```

Capture stdout. The JSON summary contains `confirmed`, `borderline`, `not_found`, `error`, `skipped`, and `companies`.
```

---

**Failure-mode documentation pattern** (from `skills/scout-run/SKILL.md` lines 151–157 — the "Failure modes" block):

```markdown
**Failure modes detect.py already handles (no skill-side handling needed):**
- `ats_provider=manual` rows → skipped silently (idempotency lock).
- All providers return NOT_FOUND → company gets `ats_provider=none` in master_targets.csv; run continues.
- Network timeout / HTTP error → bucketed as ERROR in the JSON summary; company not written.
- rapidfuzz not installed → detect.py exits 1 with install hint; skill surfaces this to user.
```

---

### `tests/test_detection.py` (test, batch)

**Analog:** `tests/test_migration.py` (fixture-driven pytest, project-root bootstrap)

---

**File header + bootstrap pattern** (from `tests/test_migration.py` lines 1–43):

```python
"""
test_detection.py — Fixture-driven tests for Phase 3 detection layer.

Covers DET-01..07, STR-02, STR-04.

Run:
  ~/.job-scout-venv/bin/python3 -m pytest tests/test_detection.py -v
  # or per-test:
  ~/.job-scout-venv/bin/python3 -m pytest tests/test_detection.py::test_two_factor_gate -x
"""
import csv
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Bootstrap project scripts on sys.path (sibling-script pattern from CONVENTIONS)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from ats.providers.base import DetectionResult, DetectionStatus  # noqa: E402
```

---

**pytest.fixture pattern** (from `tests/test_migration.py` lines 44–52):

```python
@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a minimal data_dir with master_targets.csv for detection tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Copy or generate a fixture CSV with known ats_provider states
    ...
    return data_dir
```

---

**Fixture-based integration test pattern** (from `tests/test_migration.py` lines 56–105 — one assertion per test function, descriptive names):

```python
def test_schema_version_is_v4():
    """Sanity: schema constant catches Plan 01 regression."""
    assert MASTER_TARGETS_VERSION == 4

def test_two_factor_gate_confirmed():
    """DET-03: score >= 85 → CONFIRMED."""
    ...

def test_two_factor_gate_borderline():
    """DET-03: 70 <= score < 85 → BORDERLINE."""
    ...

def test_idempotency_manual_lock():
    """DET-04: ats_provider=manual rows are NEVER overwritten, even with --force."""
    ...
```

---

**httpx.Client mock pattern** (for detection tests without live network):

```python
# In conftest.py or inline — mock the httpx.Client to return fixture payload
from unittest.mock import MagicMock

@pytest.fixture
def mock_greenhouse_client(tmp_path):
    """httpx.Client mock that returns the airbnb fixture for any .get() call."""
    fixture_path = Path(__file__).parent / "fixtures" / "ats" / "greenhouse" / "airbnb.json"
    payload = json.loads(fixture_path.read_text())
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp
    return mock_client
```

---

### `tests/conftest.py` (test config, shared fixtures)

**Analog:** `tests/test_migration.py` (same bootstrap pattern; conftest.py doesn't exist yet)

**Pattern:** conftest.py lives in `tests/` (same directory as `test_migration.py`). Uses same `PROJECT_ROOT` / `SCRIPTS_DIR` bootstrap. Exports shared fixtures so both `test_migration.py` and `test_detection.py` can import them.

```python
"""
conftest.py — Shared pytest fixtures for job-scout-plugin test suite.
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def mock_greenhouse_ok(tmp_path):
    """Shared: httpx.Client mock returning the Greenhouse airbnb fixture (200 + jobs)."""
    fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "ats" / "greenhouse" / "airbnb.json"
    payload = json.loads(fixture_path.read_text())
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp
    return mock_client
```

---

### `skills/scout-run/SKILL.md` — Step 2b addition (skill modification)

**Analog:** Existing `skills/scout-run/SKILL.md` lines 110–157 (the `[ATS-PREVIEW]` Step 2.5 block)

**Insertion point:** After Step 2 (line ~107) and before Step 2.5 (line 110). Step 2b must appear between the company selection loop and the `[ATS-PREVIEW]` block.

**Pattern to copy from Step 2.5** (lines 119–129 — the "ONE Bash call" + "capture stdout" structure):

```markdown
## Step 2b: Lazy inline detection (for unmapped companies)

For each company selected in Step 2 where `ats_provider` is empty in `master_targets.csv`:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/detect.py detect-one \
  <company_slug> \
  --name "<company_name>" \
  --data-dir "<data_dir>"
```

Capture the JSON output. Store detected results in memory for write-back in Step 8.
Do NOT write to `master_targets.csv` here — write-back happens in Step 8 after the run completes.
If `detect-one` exits non-zero or returns `status` NOT_FOUND / ERROR, set `ats_provider="none"`
for that company and continue. **The run must not stop on a detection failure.**
```

The failure-mode docblock from Step 2.5 (lines 151–157) is the template for the non-blocking constraint language above. The Bash-block structure (verbatim-runnable, single call) mirrors Step 2.5 lines 127–130.

---

### `skills/job-scout/references/file-contract.md` — add `ats_detection_review.csv` (doc modification)

**Analog:** Existing `file-contract.md` Persistent files table (lines 28–38)

**Row to add** (matches the table's `| File | Path | Owner |` schema):

```markdown
| ATS detection review | `{data_dir}/ats_detection_review.csv` | `/scout-detect` via `detect.py` (append-only). User fills `action` column after review. |
```

**Table structure to match** (lines 28–38 of file-contract.md):
```markdown
| File | Path | Owner |
|---|---|---|
| Config | `{data_dir}/config.json` | `/scout-setup` (created), user (edits) |
...
| Run telemetry log | `{data_dir}/runs.jsonl` | `/scout-run` (appends one JSON line per run...). v0.4 SCH-01. |
```
Add the new row after `runs.jsonl`, before the closing blank line of the persistent files section.

---

### `skills/job-scout/SKILL.md` — CON-08 dead reference cleanup (doc modification)

**Source of truth for locations:** RESEARCH.md CON-08 section (lines 529–540), verified by grep 2026-04-29.

**Line 46 — exact find/replace:**
- Find: `"The full step-by-step is in \`commands/scout-run.md\`."`
- Replace: `"The full step-by-step is in \`skills/scout-run/SKILL.md\`."`

**Line 105 — exact find/replace:**
- Find: `"See \`commands/scout-run.md\` 'On-demand: generate A-tier packet' for the file layout."`
- Replace: `"See \`skills/scout-run/SKILL.md\` 'On-demand: generate A-tier packet' for the file layout."`

**Acceptance gate:** `grep -rn "commands/scout-run.md" skills/` must return 0 matches after all CON-08 edits.

---

### `skills/job-scout/references/search-config.md` — CON-08 dead reference cleanup (doc modification)

**Line 28 — exact find/replace:**
- Find: `"**Budget formula** (in \`commands/scout-run.md\`):"`
- Replace: `"**Budget formula** (in \`skills/scout-run/SKILL.md\`):"`

---

## Shared Patterns

### Sibling-Script Bootstrap (2-level for `scripts/ats/` files)

**Source:** `scripts/ats/dispatcher.py` lines 50–53
**Apply to:** `scripts/ats/detect.py`

```python
# 2-level bootstrap: detect.py → ats/ → scripts/
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
```

### ImportError + venv install hint (CON-04 pattern)

**Source:** `scripts/ats/dispatcher.py` lines 38–48 and `scripts/tracker_utils.py` lines 26–37
**Apply to:** `scripts/ats/detect.py` (for both `httpx` and `rapidfuzz`)
**CON-04 rule:** Recommend `python3 -m venv ~/.job-scout-venv`, NOT `pip install --break-system-packages`.

```python
try:
    import httpx
except ImportError:
    print(
        "ERROR: httpx not installed. Install with: "
        "python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate && pip install 'httpx>=0.27,<0.29'"
        "  (or: pip install --user 'httpx>=0.27,<0.29').",
        file=sys.stderr,
    )
    sys.exit(1)
```

### Plain print() Logging

**Source:** `scripts/ats/dispatcher.py` lines 264, 173 and CONVENTIONS.md
**Apply to:** `scripts/ats/detect.py`
- Human-readable progress → stdout
- `ERROR:` / `WARNING:` prefix → stderr
- Machine-consumable JSON → LAST `print()` of each subcommand

### `os.path.expanduser()` at the boundary

**Source:** `scripts/state.py` line 76, `scripts/validate_data.py` line 289
**Apply to:** `scripts/ats/detect.py` — expand `~` exactly once at CLI argument parsing, before passing paths to any internal function.

### Worker-thread write prohibition

**Source:** `scripts/ats/dispatcher.py` lines 24–26 (docstring), CONVENTIONS.md "All tracker writes go through tracker_utils.py"
**Apply to:** `scripts/ats/detect.py`
- Worker threads (in ThreadPoolExecutor) call `provider.detect()` only — they return `DetectionResult` objects.
- All CSV mutations (`_write_back`, `_append_borderline`) happen on the main thread after all futures complete.
- All `runs.jsonl` appends happen on the main thread after CSV writes.

### PROVIDERS Registry Iteration

**Source:** `scripts/ats/__init__.py` lines 47–49
**Apply to:** `scripts/ats/detect.py`

```python
# Iterate providers in registry order (insertion order in Python 3.7+):
for provider_name, provider in PROVIDERS.items():
    result = provider.detect(company_slug, client)
    # apply _apply_name_gate() on top
    gated = _apply_name_gate(result, company_name)
    if gated.status == DetectionStatus.CONFIRMED:
        break  # stop at first confirmed provider (DET-02)
```

### DetectionResult shape (from Phase 2 substrate)

**Source:** `scripts/ats/providers/base.py` lines 44–63
**Apply to:** `scripts/ats/detect.py` `_apply_name_gate()` return values

```python
@dataclass(frozen=True)
class DetectionResult:
    provider: str
    status: DetectionStatus       # CONFIRMED | BORDERLINE | NOT_FOUND | ERROR
    board_url: Optional[str]      # canonical URL or None
    confidence: float             # 0.0–1.0 (rapidfuzz score / 100.0)
    evidence: Dict[str, Any]      # {"first_job_company_name": ..., "name_match_score": ..., ...}
```

### Greenhouse `detect()` evidence dict shape (for `_apply_name_gate`)

**Source:** `scripts/ats/providers/greenhouse.py` lines 209–219

When `greenhouse.detect()` returns BORDERLINE (200 + ≥1 job), the `evidence` dict contains:
```python
{
    "http_status": 200,
    "job_count": len(jobs),
    "first_job_company_name": jobs[0].get("company_name", ""),
    "first_job_title": jobs[0].get("title", ""),
}
```
`_apply_name_gate` reads `evidence["first_job_company_name"]` to run `token_set_ratio`.

### `load_caps_and_kill_switch` reuse

**Source:** `scripts/ats/dispatcher.py` lines 110–140
**Apply to:** `scripts/ats/detect.py`

Import and call directly — do not duplicate:
```python
from ats.dispatcher import load_caps_and_kill_switch
caps, kill_switch = load_caps_and_kill_switch(config_path)
```

### SKILL.md Bash block verbatim-runnable constraint

**Source:** CONVENTIONS.md lines 243–248 and `skills/scout-run/SKILL.md` line 129
**Apply to:** `skills/scout-detect/SKILL.md`, Step 2b addition in `skills/scout-run/SKILL.md`

Every shell snippet in a skill prompt must be runnable with no edits. Paths use `${CLAUDE_PLUGIN_ROOT}` or `<data_dir>` placeholders that the skill's prior step has already resolved.

---

## No Analog Found

All 8 files have codebase analogs. No files require falling back to RESEARCH.md patterns exclusively.

However, two implementation details have no direct codebase precedent and must be built fresh per RESEARCH.md:

| Detail | Why No Analog | RESEARCH.md Section |
|---|---|---|
| `_apply_name_gate()` with `rapidfuzz.fuzz.token_set_ratio` | rapidfuzz not yet used anywhere in codebase | Pattern 1 (lines 166–259) |
| `_normalize_for_match()` legal-suffix stripper | No string normalization utility exists yet | Pattern 1 (lines 243–258) |

---

## Metadata

**Analog search scope:** `scripts/`, `scripts/ats/`, `scripts/ats/providers/`, `skills/`, `tests/`
**Files scanned:** 13 (tracker_utils.py, state.py, dispatcher.py, runs_log.py, __init__.py, providers/base.py, providers/greenhouse.py, test_migration.py, skills/scout-run/SKILL.md, skills/scout-setup/SKILL.md, skills/job-scout/SKILL.md, skills/job-scout/references/file-contract.md, scripts/ats/preview.py)
**Pattern extraction date:** 2026-04-29

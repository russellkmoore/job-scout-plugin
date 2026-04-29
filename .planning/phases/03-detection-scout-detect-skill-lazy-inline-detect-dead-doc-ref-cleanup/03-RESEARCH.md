# Phase 3: Detection + `/scout-detect` skill + lazy inline detect + dead-doc-ref cleanup — Research

**Researched:** 2026-04-29
**Domain:** ATS slug detection, rapidfuzz fuzzy matching, master_targets.csv write coordination, skill authoring
**Confidence:** HIGH

---

## Summary

Phase 3 builds the detection layer that populates `ats_provider`, `ats_board_url`, `ats_slug_confidence`, and `last_ats_hit_date` in `master_targets.csv`. The substrate from Phase 2 is fully ready: `Provider.detect()` is defined in `providers/base.py`, Greenhouse's `detect()` is implemented and returns `DetectionResult` with `BORDERLINE` status (because Phase 2 deliberately deferred the rapidfuzz name-match half of the two-factor gate to Phase 3). The `DetectionStatus` enum already has `CONFIRMED`, `BORDERLINE`, `NOT_FOUND`, `ERROR`. Phase 3's job is to add the `rapidfuzz` name-match layer on top, build `scripts/ats/detect.py` as a CLI with `detect-one`/`detect-batch` subcommands, add the `/scout-detect` skill, hook lazy inline detection into `/scout-run` Step 2b, fix the 3 dead `commands/scout-run.md` references (CON-08), and add the two new file-contract entries (`ats_detection_review.csv` + the `detect.py` driver).

The most important architectural insight for planning: **all CSV writes that update `master_targets.csv` must happen on the SKILL (main) thread, never inside a worker thread.** The dispatcher already serializes all tracker writes; the same rule applies to CSV writes. `detect.py` reads the CSV, runs detection (which is I/O-bound but uses the same thread-safe `httpx.Client`), and collects results in memory; the SKILL (or a serialize-then-write helper in `detect.py`) writes back. This eliminates race conditions when `/scout-detect` runs concurrently against top-30 companies.

**Primary recommendation:** Build `detect.py` as a thin CLI that delegates HTTP to the existing dispatcher pattern (shared `httpx.Client`, per-provider concurrency caps), applies rapidfuzz on top of the raw `DetectionResult.confidence` value, serializes all CSV mutations to the calling process, and writes telemetry to `runs.jsonl`. The SKILL orchestrates; the script holds all deterministic logic.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DET-01 | `scripts/ats/detect.py` exposes `detect-one <company> [--name <display_name>]` and `detect-batch <csv_path> [--limit N] [--force]` CLI subcommands | CLI shape section; sibling-script pattern |
| DET-02 | Detection probes each provider in PROVIDERS registry order, returns first match passing two-factor gate | Provider iteration pattern; `PROVIDERS` registry already registry-driven |
| DET-03 | Two-factor gate: HTTP 200 + ≥1 job + name fuzzy match ≥85% (`rapidfuzz.fuzz.token_set_ratio`) | rapidfuzz section; gate architecture |
| DET-04 | Negative results cached as `ats_provider=none`; `detect-batch` skips non-empty rows unless `--force`; `ats_provider=manual` never overwritten | Idempotency section |
| DET-05 | Borderline matches (score 70–84) appended to `<data_dir>/ats_detection_review.csv` | Borderline CSV section |
| DET-06 | New skill `skills/scout-detect/SKILL.md` orchestrates batch detection on top-30 companies | Skill structure section |
| DET-07 | `/scout-run` Step 2b lazy inline detection: detect on empty `ats_provider`, write result back to CSV after run | Lazy inline section |
| STR-02 | `ats_slug_confidence` populated as 1.0 (CONFIRMED), 0.7–0.94 (BORDERLINE band), `manual` (lock); `manual` never overwritten | Confidence column section |
| STR-04 | `/scout-detect` idempotent — re-run is no-op unless `--force`; `ats_provider=manual` honored | Same as DET-04 |
| CON-08 | Fix 3 dead `commands/scout-run.md` references in skill-doc files being modified for the new skill | Dead-reference section; exact line locations documented |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Two-factor gate logic (HTTP probe + fuzzy match) | Script (`detect.py`) | — | Deterministic; must be testable via fixture; no LLM judgment |
| Provider iteration order | Script (`detect.py`) → `PROVIDERS` registry | — | Registry-driven per DSP-09/PRV-09; `detect.py` iterates `PROVIDERS.items()` |
| CSV read/write of master_targets.csv | Script (`detect.py`) | SKILL (for final write-back call) | Serialized, deterministic; never from worker threads |
| Borderline CSV append (`ats_detection_review.csv`) | Script (`detect.py`) | — | Append-only, same pattern as `runs.jsonl` |
| `runs.jsonl` telemetry appends | Script (`detect.py` calls `runs_log.append_run`) | — | Same runs_log.py module; one line per detect-batch run |
| Batch orchestration (top-30 order, user prompting) | SKILL (`/scout-detect/SKILL.md`) | — | LLM orchestrates; script provides subcommands |
| Lazy inline detection trigger | SKILL (`/scout-run` Step 2b) | Script (`detect-one`) | SKILL decides when to trigger; script does the HTTP work |
| Skill structure + frontmatter | SKILL files | — | Markdown + YAML; references established patterns |
| Dead doc reference cleanup (CON-08) | Doc edits (`SKILL.md`, `search-config.md`) | — | Mechanical find/replace; no logic change |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `rapidfuzz` | [VERIFIED: NOT yet installed in `~/.job-scout-venv`] latest | Company name fuzzy matching for two-factor gate | Already in locked stack per PROJECT.md and SUMMARY.md (researched 2026-04-27); `token_set_ratio` handles word-order variation, abbreviations, "Inc."/"Corp." suffixes |
| `httpx` | 0.28.1 [VERIFIED: venv] | HTTP probes for detection | Same shared client as dispatcher; thread-safe sync `Client` |
| `concurrent.futures` | stdlib | Concurrent detection probes (same ThreadPoolExecutor pattern) | Phase 2 dispatcher already uses this |
| `threading.Semaphore` | stdlib | Per-provider caps during batch detection | Same `_SEMAPHORES` from dispatcher |
| `csv` / `pandas` | stdlib / existing | Read/write `master_targets.csv` | `validate_data.py` uses pandas for CSV; `detect.py` should follow same pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `rapidfuzz.fuzz.token_set_ratio` | — | Two-factor gate name match | Always — handles "Acme Inc." vs "Acme", "ACME Corp" vs "Acme", word-order invariant |
| `rapidfuzz.fuzz.token_sort_ratio` | — | Secondary match for borderline cases | Optional: can run both and take max to widen the borderline window |

**Installation (Wave 0 task — must run before detection tests):**
```bash
~/.job-scout-venv/bin/pip install rapidfuzz
```

Or install hint to add to `detect.py` `ImportError` block:
```
python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate && pip install rapidfuzz
```

**Version verification:** [VERIFIED: rapidfuzz not in venv as of 2026-04-29 — must be installed in Wave 0]

---

## Architecture Patterns

### System Architecture Diagram

```
/scout-detect SKILL.md
    │
    │  Step 1: Resolve data_dir, read master_targets.csv
    │
    │  Step 2: Call detect-batch  ──────────────────────────────────────────────┐
    │                                                                             │
    ▼                                                                             ▼
scripts/ats/detect.py detect-batch                           scripts/ats/detect.py detect-one
    │                                                                             │
    │  For each company in top-N:                             For one company:    │
    │    ┌─────────────────────────┐                              ┌──────────────┐│
    │    │  For each provider in   │                              │ For each     ││
    │    │  PROVIDERS registry:    │                              │ provider:    ││
    │    │    provider.detect(     │                              │  detect()    ││
    │    │      slug, name, client)│                              │  + rapidfuzz ││
    │    │    + rapidfuzz name     │                              └──────────────┘│
    │    │      match layer        │                                              │
    │    │    → DetectionResult    │                         DetectionResult ─────┘
    │    └─────────────────────────┘
    │
    │  Decision tree per company:
    │    CONFIRMED (≥85%)  → update master_targets.csv row (ats_provider, ats_board_url,
    │                         ats_slug_confidence=score/100.0, last_ats_hit_date=TODAY)
    │    BORDERLINE (70-84)→ append to ats_detection_review.csv; skip master_targets write
    │    NOT_FOUND / ERROR → write ats_provider="none" to master_targets.csv
    │
    │  After all companies processed:
    │    → Append ONE line to runs.jsonl (detection telemetry)
    │    → Print JSON summary to stdout
    │
    ▼
/scout-run SKILL.md Step 2b (lazy inline)
    │
    │  For each company in today's slate where ats_provider == "":
    │    Call detect-one <company_slug> --name <display_name>
    │    Write result back to master_targets.csv AFTER the run completes
    │                                                                         ▲
    └─────────── master_targets.csv (single write-back after all detections) ─┘
```

### Recommended Project Structure

```
scripts/ats/
├── detect.py              # NEW: detect-one + detect-batch CLI
├── __init__.py            # PROVIDERS registry (existing)
├── dispatcher.py          # fetch_all (existing)
├── normalize.py           # Listing dataclass (existing)
├── preview.py             # Phase 2 [ATS-PREVIEW] driver (existing)
├── runs_log.py            # append_run (existing)
└── providers/
    ├── base.py            # Provider Protocol + DetectionResult (existing)
    └── greenhouse.py      # detect() + fetch() (existing)

skills/
├── scout-detect/          # NEW skill directory
│   └── SKILL.md           # NEW: batch detection orchestration
├── scout-run/
│   └── SKILL.md           # MODIFIED: add Step 2b lazy inline detect
└── job-scout/
    ├── SKILL.md           # MODIFIED: fix CON-08 dead references (lines 46, 105)
    └── references/
        └── search-config.md  # MODIFIED: fix CON-08 dead reference (line 28)

skills/job-scout/references/
└── file-contract.md       # MODIFIED: add ats_detection_review.csv entry
```

---

## Pattern 1: Two-Factor Gate Implementation

**What:** `detect.py`'s gate function applies rapidfuzz on top of the raw `DetectionResult` from `provider.detect()`.

**The critical insight about current greenhouse.py:** Greenhouse's `detect()` already returns `BORDERLINE` with `confidence=0.85` when there are ≥1 jobs (HTTP 200 + jobs present). It stores `first_job_company_name` in `evidence`. Phase 3's gate function reads that evidence field and runs `token_set_ratio` against the input company name. If ≥85, elevates to `CONFIRMED`. The Phase 2 implementation was intentionally designed this way — see greenhouse.py line 209-219 and the docstring at lines 146-153.

```python
# Source: scripts/ats/providers/base.py + scripts/ats/providers/greenhouse.py (Phase 2)
# Pattern: gate() in detect.py applies rapidfuzz on top of DetectionResult.evidence

try:
    from rapidfuzz import fuzz
except ImportError:
    print(
        "ERROR: rapidfuzz not installed. Install with: "
        "python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate "
        "&& pip install rapidfuzz  "
        "(or: pip install --user rapidfuzz).",
        file=sys.stderr,
    )
    sys.exit(1)

def _apply_name_gate(
    raw: "DetectionResult",
    company_name: str,
    high_threshold: float = 85.0,
    borderline_low: float = 70.0,
) -> "DetectionResult":
    """Apply the rapidfuzz name-match half of the two-factor gate.

    Called AFTER provider.detect() returns. The provider already checked
    HTTP 200 + ≥1 job (factor A). This function applies factor B: the
    company name in the API response must fuzzy-match the input name ≥85%.

    Returns a new DetectionResult with:
      - CONFIRMED if score >= high_threshold
      - BORDERLINE if borderline_low <= score < high_threshold
      - NOT_FOUND if score < borderline_low (but raw was CONFIRMED/BORDERLINE)
      - Passes through NOT_FOUND / ERROR unchanged (no name to match)
    """
    if raw.status in (DetectionStatus.NOT_FOUND, DetectionStatus.ERROR):
        return raw  # pass through — no name evidence to score

    # Extract the returned company name from evidence dict
    returned_name = raw.evidence.get("first_job_company_name", "")
    if not returned_name:
        # No company name in response — treat as BORDERLINE with low confidence
        # (Greenhouse always includes company_name; absence means wildcard catch-all)
        score = 0.0
    else:
        score = fuzz.token_set_ratio(
            _normalize_for_match(company_name),
            _normalize_for_match(returned_name),
        )

    confidence = score / 100.0  # store as 0.0-1.0 in ats_slug_confidence

    if score >= high_threshold:
        return DetectionResult(
            provider=raw.provider,
            status=DetectionStatus.CONFIRMED,
            board_url=raw.board_url,
            confidence=confidence,
            evidence={**raw.evidence, "name_match_score": score, "input_name": company_name, "returned_name": returned_name},
        )
    elif score >= borderline_low:
        return DetectionResult(
            provider=raw.provider,
            status=DetectionStatus.BORDERLINE,
            board_url=raw.board_url,
            confidence=confidence,
            evidence={**raw.evidence, "name_match_score": score, "input_name": company_name, "returned_name": returned_name},
        )
    else:
        return DetectionResult(
            provider=raw.provider,
            status=DetectionStatus.NOT_FOUND,
            board_url=None,
            confidence=confidence,
            evidence={**raw.evidence, "name_match_score": score, "input_name": company_name, "returned_name": returned_name},
        )


def _normalize_for_match(name: str) -> str:
    """Lowercase, strip common legal suffixes, strip punctuation.

    'Acme Inc.' -> 'acme'
    'ACME Corp' -> 'acme'
    'The Acme Company LLC' -> 'acme company'
    """
    import re
    name = name.lower().strip()
    # Strip trailing legal entity suffixes
    name = re.sub(
        r'\b(inc\.?|corp\.?|llc\.?|ltd\.?|co\.?|company|the\b)', '', name
    ).strip()
    # Collapse whitespace + strip non-alpha
    name = re.sub(r'[^a-z0-9\s]', '', name)
    return re.sub(r'\s+', ' ', name).strip()
```

**Edge cases the normalizer must handle:**
- "Inc." / "Inc" / ", Inc" (trailing comma-space patterns)
- "Corporation" vs "Corp"
- Leading "The " — "The Trade Desk" vs "Trade Desk"
- CamelCase slugs: `thetradedesk` → needs word-boundary awareness (NOT handled by `_normalize_for_match` — the slug is passed raw, the `company_name` from the response is what gets normalized)
- All-caps slugs: `AIRBNB` → lowercase handles this
- Special chars in display name: "C&A" → strip non-alpha
- Unicode accents: "Nestlé" → normalize to ASCII? (low priority, but `str.casefold()` is better than `str.lower()` for international names)

---

## Pattern 2: `detect.py` CLI Shape

```python
# Usage (from REQUIREMENTS.md DET-01):
#   python3 scripts/ats/detect.py detect-one airbnb [--name "Airbnb"]
#   python3 scripts/ats/detect.py detect-batch <data_dir>/master_targets.csv
#       [--limit 30] [--force] [--data-dir <data_dir>]

# detect-one output (stdout, JSON):
{
  "company_slug": "airbnb",
  "company_name": "Airbnb",
  "provider": "greenhouse",
  "status": "CONFIRMED",      # or BORDERLINE / NOT_FOUND / ERROR
  "board_url": "https://boards-api.greenhouse.io/v1/boards/airbnb/jobs?content=true",
  "confidence": 0.97,          # 0.0-1.0
  "name_match_score": 97.0,
  "evidence": {...}
}

# detect-batch output (stdout, JSON):
{
  "total": 30,
  "confirmed": 18,
  "borderline": 4,
  "not_found": 6,
  "error": 2,
  "skipped": 0,              # rows skipped because ats_provider already set
  "wall_clock_seconds": 12.4,
  "companies": [...]         # per-company result list (same shape as detect-one)
}
```

**Key constraints:**
- `detect-one` must accept a `--name` flag because the slug (from `ats_board_url` path) may differ from the display name (`company_name` column). Example: slug `airbnb` but name "Airbnb, Inc."
- `detect-batch` reads `master_targets.csv` for `company_name` (used as `--name`) and derives the slug from `company_name` normalized, OR from existing `ats_board_url` if non-empty
- `--data-dir` is needed by `detect-batch` to write back to the CSV and to find `config.json` for concurrency caps

---

## Pattern 3: Idempotency + `ats_provider=manual` Lock

**What:** `detect-batch` must skip rows where `ats_provider` is non-empty UNLESS `--force` is passed. `ats_provider=manual` rows MUST NEVER be overwritten regardless of `--force`.

```python
# In detect-batch iteration:
def _should_skip(row: dict, force: bool) -> tuple[bool, str]:
    """Returns (skip_bool, reason_string)."""
    ats_prov = (row.get("ats_provider") or "").strip()
    if ats_prov == "manual":
        return True, "manual-lock"
    if ats_prov and not force:
        return True, f"already-set:{ats_prov}"
    # Check 30-day re-detection window for non-forced re-runs
    last_hit = (row.get("last_ats_hit_date") or "").strip()
    if ats_prov and last_hit and not force:
        try:
            delta = (date.today() - date.fromisoformat(last_hit)).days
            if delta < 30:
                return True, f"fresh-detection:{delta}d-ago"
        except ValueError:
            pass  # malformed date — don't skip
    return False, ""
```

**Note on ROADMAP SC-3 idempotency check:** The ROADMAP says "re-running `/scout-detect` on the same CSV is a no-op." The `last_ats_hit_date` column (already in schema.py) makes this precise: skip if `ats_provider` non-empty AND `last_ats_hit_date` is within 30 days AND not `--force`. This matches the "idempotent re-run" requirement while still allowing refresh when data is stale.

---

## Pattern 4: CSV Write-Back Safety

**Critical constraint:** `master_targets.csv` must never be written from a worker thread. All detection probes can run concurrently via ThreadPoolExecutor (reusing the dispatcher's semaphore pattern), but the CSV write-back must happen on the calling (main) thread after all probes complete.

```
detect-batch flow:

1. Read master_targets.csv into list[dict] on main thread
2. Build list of (company_slug, company_name, provider_name) detection tasks
3. Submit all tasks to ThreadPoolExecutor (reusing dispatcher._SEMAPHORES)
4. Collect all DetectionResult objects into results list
5. Apply _apply_name_gate on each result (on main thread — no I/O)
6. Write updated master_targets.csv ONCE on main thread
7. Append ats_detection_review.csv entries ONCE on main thread
8. Append runs.jsonl ONCE on main thread
```

**Why not reuse `dispatcher.fetch_all`?** The detection phase uses `provider.detect()`, not `provider.fetch()`. The dispatcher's `_execute_one` calls `fetch()` and returns `FetchOutcome`. Detection needs `detect()` and returns `DetectionResult`. A separate execution helper in `detect.py` follows the same ThreadPoolExecutor + semaphore pattern but calls `detect()` instead.

The alternative (creating a thin wrapper that maps `detect()` through `_execute_one`) would be more complex and harder to debug. Keep detection separate from fetching.

---

## Pattern 5: `ats_detection_review.csv` Schema

```
# NEW file — must be added to file-contract.md as a persistent file (not per-run)
# Path: <data_dir>/ats_detection_review.csv
# Owner: /scout-detect + detect.py (append-only)
# Consumed by: user (manual review)

Columns:
  detected_date, company_name, company_slug, provider, name_match_score,
  ats_board_url, returned_company_name, action
  
# action defaults to "" — user fills in "accept" or "skip" after review
```

**Append pattern:** Use Python's `csv` module in append mode (`'a'`) with `newline=''`. Write header only if file doesn't exist. Same pattern as `runs.jsonl` append-only (never rewrite).

---

## Pattern 6: Lazy Inline Detection in `/scout-run`

**Where:** Between Step 2 (existing Pass 1 company-first deep-dive) and Step 2.5 ([ATS-PREVIEW]). Call it "Step 2b."

**Trigger condition:** Company in today's slate (selected by `companies_per_day` sort) has empty `ats_provider`.

**Key constraint — non-blocking:** If detection fails (all providers return NOT_FOUND or ERROR), the run must continue. Write `ats_provider=none_detected` [VERIFIED: REQUIREMENTS.md DET-04 uses `ats_provider=none`] and proceed. Do NOT abort the run.

**Write-back timing:** The lazy inline detect results must be written back to `master_targets.csv` AFTER the full run completes (in Step 8: Update master_targets.csv), not inline during Step 2. This avoids a partial-write state if the run is interrupted mid-pass.

**Skill prompt pattern for Step 2b:**
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
Do NOT write to master_targets.csv here — write-back happens in Step 8 after the run.
If detect-one exits non-zero or returns status NOT_FOUND/ERROR, set ats_provider="none"
for that company and continue. The run must not stop on a detection failure.
```

**What "company_slug" means for detect-one:** In the lazy inline context, the slug is derived from the company's row — typically normalized from `company_name` (lowercase, spaces→hyphen, strip special chars). For Phase 3 with only Greenhouse in the registry, this matches how Greenhouse slugs work. The `detect-one` command can derive the slug from `--name` using `_normalize_for_match(name).replace(' ', '-')` as a fallback slug when no explicit slug argument is given.

---

## Pattern 7: Detection Telemetry to `runs.jsonl`

**What:** `detect-batch` appends ONE detection-run line to `runs.jsonl` using `runs_log.append_run`. The line schema must be distinguishable from a `/scout-run` fetch line.

```python
# Suggested telemetry structure for detect-batch run (appended to runs.jsonl)
{
  "timestamp": "2026-04-29T...",
  "run_type": "detect_batch",         # distinguishes from "scout_run"
  "wall_clock_seconds": 12.4,
  "companies_total": 30,
  "confirmed": 18,
  "borderline": 4,
  "not_found": 6,
  "error": 2,
  "skipped": 0,
  "per_company": {
    "airbnb": {"provider": "greenhouse", "status": "CONFIRMED", "score": 97.0},
    "stripe": {"provider": "greenhouse", "status": "CONFIRMED", "score": 92.0},
    "acme":   {"provider": "", "status": "NOT_FOUND", "score": 0.0},
    ...
  }
}
```

**Note on `runs_log.append_run` signature:** The existing `append_run` function signature (in `runs_log.py`) is designed for fetch outcomes, not detection outcomes. `detect.py` should call `append_run` with a `run_type="detect_batch"` parameter, OR write the detection telemetry line directly using the same open-append-flush pattern. Recommend extending `append_run` to accept an optional `extra_fields: dict` parameter, or writing a separate `append_detection_run()` function in `runs_log.py`.

**DET-07 per REQUIREMENTS.md says:** "Detection telemetry to runs.jsonl — append-only line per detection attempt with company, provider tested, outcome (hit/miss/error), match score." This is per-attempt, meaning one line per company per provider tested (not one line for the whole batch). However, for `/scout-detect` the more useful granularity is per-company (the result after all providers are tried). Plan should clarify this: "one line per `/scout-detect` invocation containing per-company results" vs "one line per (company, provider) attempt." The ROADMAP Phase 3 SC-4 reads "Borderline matches appear in `ats_detection_review.csv`" which is per-company, not per-provider-attempt. Recommend: ONE line per detect-batch run + per-company breakdown (not per-provider-attempt, which would be noisy).

---

## Pattern 8: `/scout-detect` Skill Structure

The skill follows the established `SKILL.md` format from `scout-run` and `scout-setup`.

**Frontmatter:**
```yaml
---
name: scout-detect
description: Detect ATS providers for top-connection companies and populate ats_provider + ats_board_url in master_targets.csv. Triggers when the user types `/scout-detect` or asks to "detect job boards", "find which ATS my target companies use", "populate ATS fields".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, TodoWrite
version: 0.4.0
---
```

**Step structure (for planner):**
1. Resolve `data_dir` via `state.py resolve`
2. Validate data dir via `validate_data.py`
3. Read `master_targets.csv` and identify the top-N companies (sort by `linkedin_connection_count` desc, take `--limit` rows, default 30)
4. Call `detect-batch` — ONE Bash call with the CSV path and limit
5. Review the borderline CSV if any borderline matches were found
6. Summarize results to user

**Key skill-level decisions the planner must encode:**
- The `--limit 30` is the default "top-30 connection-weighted" behavior; user can pass `--all` to detect all companies
- After `/scout-detect` runs, the next `/scout-run` Step 2.5 will immediately start producing real Greenhouse listings (because `ats_provider="greenhouse"` is now populated)
- The skill does NOT run `/scout-run` — it only populates the detection columns

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Company name fuzzy matching | Custom Levenshtein / edit-distance | `rapidfuzz.fuzz.token_set_ratio` | Handles word order, "Inc." suffix, abbreviations — all cases that simple Levenshtein misses |
| CSV read/write | ad-hoc `open()` + split | pandas (existing) or stdlib `csv.DictReader`/`DictWriter` | `master_targets.csv` has variable user-added columns; pandas handles column preservation correctly; same pattern as `validate_data.py` |
| Concurrent HTTP probes | asyncio / aiohttp | `concurrent.futures.ThreadPoolExecutor` + `threading.Semaphore` | Reuse Phase 2 dispatcher pattern; consistency; ~30 companies is below async crossover |
| Detection review tracking | Per-run files / stdout | `ats_detection_review.csv` (append-only) | User needs persistent review history across multiple detection runs |

---

## Common Pitfalls

### Pitfall 1: Writing master_targets.csv from Worker Threads
**What goes wrong:** `detect-batch` submits detection tasks to ThreadPoolExecutor; a worker writes the CSV result immediately when detection succeeds. Two workers writing simultaneously corrupt the CSV.
**Why it happens:** Treating detection results as immediately-writable is natural but incorrect. The dispatcher pattern already serializes tracker writes; detection CSV writes must follow the same rule.
**How to avoid:** Collect all `DetectionResult` objects from futures into a list. Apply the gate function. Write the CSV ONCE on the main thread after all futures complete.
**Warning signs:** CSV rows disappearing or having garbled data on a detect-batch run against many companies.

### Pitfall 2: Slug Derivation Mismatch
**What goes wrong:** For `detect-one`, the "slug" passed to `provider.detect()` is derived from the company name, but the actual Greenhouse slug for a company may differ significantly. "Lululemon Athletica" → slug guess `lululemon-athletica` but actual Greenhouse slug is `lululemon`.
**Why it happens:** Company names don't map deterministically to ATS slugs. The slug is what Greenhouse registered, not what the company display name normalizes to.
**How to avoid:** In `detect-batch` context, if `ats_board_url` is already partially populated (e.g., from a prior partial detect run or from the existing Phase 2 preview code), use the slug from that URL. When truly guessing, try the most minimal normalization first (just lowercase + strip special chars, no hyphen-splitting). `detect.py` should document that slug guessing has a high miss rate — the canonical source is `ats_board_url`.
**Warning signs:** Many NOT_FOUND results for companies that are clearly on Greenhouse.

### Pitfall 3: Zero-Job Greenhouse Boards
**What goes wrong:** A valid Greenhouse slug returns HTTP 200 with 0 jobs. The current `greenhouse.detect()` returns `BORDERLINE` with `confidence=0.5` for this case. The gate function sees `evidence.job_count=0` and `first_job_company_name=""`, so `token_set_ratio` returns 0. Result: `NOT_FOUND`. But the company IS on Greenhouse — they just have no open roles.
**Why it happens:** The two-factor gate requires ≥1 job to confirm (per REQUIREMENTS.md DET-03 "HTTP 200 + ≥1 job"). A zero-job board can't provide the company-name evidence needed for factor B.
**How to avoid:** Treat zero-job boards as `BORDERLINE` explicitly (write to `ats_detection_review.csv` with a `no_open_roles` flag) rather than `NOT_FOUND`. The distinction matters: `NOT_FOUND` → `ats_provider=none`, but a zero-job board → `ats_provider=greenhouse` should eventually be set when they have roles again. Plan must encode this as a special case: "HTTP 200 + 0 jobs → BORDERLINE (zero_roles), write to review CSV with proposed `ats_board_url`, do not write `ats_provider=none`."
**Warning signs:** Companies you know are on Greenhouse showing `ats_provider=none` after a detect-batch run.

### Pitfall 4: Detecting with Wrong/Generic Slugs
**What goes wrong:** For companies without an existing `ats_board_url`, the detect code must guess a slug from `company_name`. "Stripe" → `stripe` (correct). "Expedia Group" → `expedia-group` but actual slug is `expediagroup`. The Greenhouse API returns 200 + jobs for `expedia-group` if they happen to have a real board there — and the company name fuzzy matches "Expedia Group" → CONFIRMED for the wrong slug.
**Why it happens:** Greenhouse does not 404 on random slugs — it sometimes returns 200 with a wildcard catch-all. The two-factor name gate is the defense, but only if the returned `company_name` is examined.
**How to avoid:** Always check `evidence.first_job_company_name` against the input name. If the score is ≥85%, accept. The `_normalize_for_match` function must strip "Group" / "Inc" / "Corp" from both sides. If a slug returns 200 + jobs but no `company_name` in the response, reject.
**Warning signs:** `ats_board_url` pointing to a company that clearly isn't the right one.

### Pitfall 5: Not Differentiating `none` vs `none_detected`
**What goes wrong:** REQUIREMENTS.md DET-04 says negative results are cached as `ats_provider=none`. But CLAUDE.md locked decisions say "none_detected is a valid `ats_provider` value." There's a naming discrepancy.
**Authoritative answer:** REQUIREMENTS.md DET-04 uses `ats_provider=none`. CLAUDE.md locked decisions say `none_detected`. Pick one and use it consistently throughout detect.py, SKILL.md, and any grep gates. **Recommend `none` (shorter, in REQUIREMENTS.md).** The CLAUDE.md note says `none_detected` is valid — it may have been written before REQUIREMENTS.md was finalized. The planner should pick `none` (consistent with DET-04) and document the choice.
**Warning signs:** Detection code using `none_detected` while grep gates check for `none` (or vice versa), causing false-positive idempotency skips.

### Pitfall 6: Missing `--data-dir` on `detect-one` in Lazy Inline
**What goes wrong:** In the lazy inline path (`/scout-run` Step 2b), `detect-one` needs to know where to find `config.json` for concurrency caps. Without `--data-dir`, it uses DEFAULT_PROVIDER_CAPS and has no way to append to `runs.jsonl` or `ats_detection_review.csv`.
**How to avoid:** `detect-one` always accepts `--data-dir`. It's optional (falls back to defaults), but the skill prompt must always pass it. Also: the lazy inline path does NOT append to `runs.jsonl` per-company — only `detect-batch` does. The lazy inline results are captured in memory and written back to the CSV in Step 8; a single telemetry line can be appended at the end of the `/scout-run` run (as part of the existing preview.py summary, or separately).

### Pitfall 7: `ats_detection_review.csv` Not in `file-contract.md`
**What goes wrong:** A new persistent file is created but not added to `references/file-contract.md`. Future skill invocations can't find it. The "single source of truth" rule is violated.
**How to avoid:** Phase 3 must add `ats_detection_review.csv` to the Persistent files table in `file-contract.md` as a Wave 0 or Wave 1 task, BEFORE any code writes it.

---

## CON-08: Dead `commands/scout-run.md` References

**Verified locations** [VERIFIED: grep as of 2026-04-29]:
1. `skills/job-scout/SKILL.md:46` — "The full step-by-step is in `commands/scout-run.md`."
   **Fix:** → "The full step-by-step is in `skills/scout-run/SKILL.md`."

2. `skills/job-scout/SKILL.md:105` — "See `commands/scout-run.md` 'On-demand: generate A-tier packet' for the file layout."
   **Fix:** → "See `skills/scout-run/SKILL.md` 'On-demand: generate A-tier packet' for the file layout."

3. `skills/job-scout/references/search-config.md:28` — "**Budget formula** (in `commands/scout-run.md`):"
   **Fix:** → "**Budget formula** (in `skills/scout-run/SKILL.md`):"

These files will already be opened for Phase 3 work (modifying `skills/job-scout/SKILL.md` to acknowledge the new `/scout-detect` skill under reference docs, and modifying `search-config.md` if the `/scout-detect` skill mentions budget strategy). The CON-08 fixes are 3-line edits; fold them into the same commits.

**Acceptance grep gate (plan-checker can verify):**
```bash
grep -rn "commands/scout-run.md" skills/
# Expected: 0 matches
```

---

## Code Examples

### detect.py CLI dispatch skeleton

```python
# Source: patterns from scripts/state.py + scripts/ats/dispatcher.py (Phase 2)
import json
import os
import sys

# Sibling-script bootstrap (2-level — file → ats → scripts)
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from ats import PROVIDERS
from ats.providers.base import DetectionStatus, DetectionResult
from ats.runs_log import append_run

try:
    from rapidfuzz import fuzz
except ImportError:
    print(
        "ERROR: rapidfuzz not installed. Install with: "
        "python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate "
        "&& pip install rapidfuzz  (or: pip install --user rapidfuzz).",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import httpx
except ImportError:
    print(
        "ERROR: httpx not installed. Install with: "
        "python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate "
        "&& pip install 'httpx>=0.27,<0.29'  (or: pip install --user 'httpx>=0.27,<0.29').",
        file=sys.stderr,
    )
    sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 detect.py <detect-one|detect-batch> [args...]", file=sys.stderr)
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

### Confidence → `ats_slug_confidence` mapping

```python
# Source: STR-02 requirement + DetectionStatus enum in base.py
def _confidence_to_csv(result: "DetectionResult") -> str:
    """Map DetectionResult to the ats_slug_confidence CSV value.

    CONFIRMED → str(round(result.confidence, 4))   e.g. "0.97"
    BORDERLINE → str(round(result.confidence, 4))  e.g. "0.78"
    NOT_FOUND  → ""  (empty — no confidence to store)
    ERROR      → ""  (empty — detection did not complete)
    manual     → "manual"  (only written by user, never by detect.py)
    """
    if result.status in (DetectionStatus.CONFIRMED, DetectionStatus.BORDERLINE):
        return str(round(result.confidence, 4))
    return ""
```

### CSV write-back pattern

```python
# Write updated rows back to master_targets.csv
# Must preserve user-added columns (same pattern as validate_data.py)
import csv

def _write_back(csv_path: str, rows: list[dict], fieldnames: list[str]) -> None:
    """Write updated rows to master_targets.csv preserving column order."""
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
```

---

## Runtime State Inventory

This is a code-build phase, not a rename/refactor. No runtime state inventory is needed.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `httpx` | Detection HTTP probes | ✓ | 0.28.1 [VERIFIED: venv] | — |
| `rapidfuzz` | Two-factor name gate | ✗ | — [VERIFIED: not in venv] | NO FALLBACK — must install in Wave 0 |
| `pandas` | CSV read/write (if reusing validate_data.py pattern) | ✓ | 3.0.2 [VERIFIED: venv per STATE.md] | stdlib `csv.DictReader` |
| `pytest` | Fixture tests | ✓ | 9.0.3 [VERIFIED: venv per STATE.md] | — |

**Missing dependencies with no fallback:**
- `rapidfuzz` — must be installed before any detection test can run. Wave 0 of Phase 3 plan must include: `~/.job-scout-venv/bin/pip install rapidfuzz`

**Missing dependencies with fallback:**
- None.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | none (invoke directly) |
| Quick run command | `~/.job-scout-venv/bin/python3 -m pytest tests/test_detection.py --tb=short -q` |
| Full suite command | `~/.job-scout-venv/bin/python3 -m pytest tests/ --tb=short -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DET-01 | `detect-one` and `detect-batch` CLI subcommands parse args correctly | unit | `pytest tests/test_detection.py::test_cli_dispatch -x` | ❌ Wave 0 |
| DET-02 | Provider iteration stops at first CONFIRMED result | unit | `pytest tests/test_detection.py::test_provider_iteration -x` | ❌ Wave 0 |
| DET-03 | `token_set_ratio ≥ 85` → CONFIRMED; 70–84 → BORDERLINE; <70 → NOT_FOUND | unit | `pytest tests/test_detection.py::test_two_factor_gate -x` | ❌ Wave 0 |
| DET-04 | `detect-batch` skips rows with `ats_provider` set; `manual` never overwritten; `--force` overrides non-manual | unit | `pytest tests/test_detection.py::test_idempotency -x` | ❌ Wave 0 |
| DET-05 | Borderline result appended to `ats_detection_review.csv`; not written to master_targets | unit | `pytest tests/test_detection.py::test_borderline_csv -x` | ❌ Wave 0 |
| DET-03 (gate) | Greenhouse fixture + name match → CONFIRMED result | integration (fixture) | `pytest tests/test_detection.py::test_greenhouse_fixture_roundtrip -x` | ❌ Wave 0 |
| STR-02 | `ats_slug_confidence` column written as float 0.0–1.0 for CONFIRMED; empty for NOT_FOUND | unit | `pytest tests/test_detection.py::test_confidence_column -x` | ❌ Wave 0 |
| CON-08 | No `commands/scout-run.md` references in skills/ | grep gate | `grep -rn "commands/scout-run.md" skills/` → 0 matches | n/a (grep) |
| DET-06 | `/scout-detect` skill file exists with valid frontmatter | smoke | `grep "^name: scout-detect" skills/scout-detect/SKILL.md` | ❌ Wave 0 |
| DET-07 | runs.jsonl updated after detect-batch; line contains `run_type`, company results | unit | `pytest tests/test_detection.py::test_detection_telemetry -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `~/.job-scout-venv/bin/python3 -m pytest tests/test_detection.py --tb=short -q`
- **Per wave merge:** `~/.job-scout-venv/bin/python3 -m pytest tests/ --tb=short -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_detection.py` — covers DET-01..07, STR-02 (new file needed)
- [ ] `~/.job-scout-venv/bin/pip install rapidfuzz` — must run before any test
- [ ] `skills/scout-detect/SKILL.md` — new skill directory and file

### What Can Be Tested Without Network

Use the existing `tests/fixtures/ats/greenhouse/airbnb.json` fixture for the integration test. `detect()` is called against a mocked `httpx.Client` that returns the fixture payload. This tests the full gate pipeline (HTTP → evidence → rapidfuzz → DetectionResult) without live network calls.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `detect.py` can reuse the Phase 2 `threading.Semaphore` caps from `dispatcher._SEMAPHORES` rather than creating new semaphores | Pattern 4 | If detection and fetch share the same semaphore, concurrent detect-batch + scout-run could starve each other. Mitigation: detect.py has its own semaphore init from `load_caps_and_kill_switch`. |
| A2 | `csv.DictWriter` with `extrasaction="ignore"` safely drops columns not in fieldnames | Pattern 4 | Could silently drop user-added columns if fieldnames list is incomplete. Mitigation: read all column names from existing CSV header before writing back. |
| A3 | The `company_name` column in master_targets.csv is always populated (never empty) | Pattern 2 | Empty names would produce empty `token_set_ratio` inputs → 0 score → NOT_FOUND for valid companies. Mitigation: skip rows with empty company_name. |
| A4 | rapidfuzz `token_set_ratio` handles Unicode company names (accents, non-ASCII) correctly | Pattern 1 | Could produce incorrect scores for "Nestlé" vs "Nestle". Mitigation: use `str.casefold()` in `_normalize_for_match`. |

---

## Open Questions

1. **`none` vs `none_detected` for negative cache value**
   - What we know: REQUIREMENTS.md DET-04 says `ats_provider=none`; CLAUDE.md locked decisions say `none_detected` is a valid value
   - What's unclear: which string should actually be written; grep gates in later phases need to know
   - Recommendation: Use `none` (shorter, in REQUIREMENTS.md). Document the choice explicitly in detect.py and the SKILL. Note in plan comments that `none_detected` was a pre-REQUIREMENTS draft and `none` wins.

2. **Zero-job Greenhouse boards: BORDERLINE or NOT_FOUND?**
   - What we know: DET-03 requires "≥1 job" as part of the gate; a zero-job board can't satisfy this
   - What's unclear: should a valid company on Greenhouse with 0 current openings get `ats_provider=none` or something more informative?
   - Recommendation: Write `ats_provider="greenhouse"` (but NOT `ats_slug_confidence` since we can't confirm) and `ats_board_url` populated, then add a `zero_open_roles` note to the detection review CSV. The company IS on Greenhouse; it just has no openings right now. Phase 4 fetch will handle this correctly (OK_ZERO outcome).

3. **How to derive slug for detect-one in the lazy inline path**
   - What we know: The slug must be passed to `provider.detect(slug, name, client)`; in the lazy inline context we only have `company_name` from master_targets
   - What's unclear: Is slug normalization good enough, or should we try multiple slug variants?
   - Recommendation: Try the simplest normalization first (lowercase, alphanumeric + hyphen, no "inc"/"corp"). If Phase 4 shows high miss rates, add a "try common suffixes" loop. Keep it simple for Phase 3.

---

## Sources

### Primary (HIGH confidence)
- `scripts/ats/providers/base.py` — `DetectionStatus`, `DetectionResult`, `Provider.detect()` signature — verified live as of 2026-04-29
- `scripts/ats/providers/greenhouse.py` — `detect()` implementation, `evidence` dict shape, BORDERLINE status on 200+jobs — verified live as of 2026-04-29
- `scripts/ats/__init__.py` — `PROVIDERS` registry structure — verified live as of 2026-04-29
- `scripts/schema.py:22–36` — `MASTER_TARGETS_COLUMNS` including `ats_provider`, `ats_board_url`, `ats_slug_confidence`, `last_ats_hit_date` — verified live
- `.planning/REQUIREMENTS.md:34–41` — DET-01..07, STR-02, STR-04, CON-08 requirements text — authoritative
- `.planning/ROADMAP.md:75–89` — Phase 3 goal, success criteria — authoritative
- `.planning/phases/02-provider-protocol-greenhouse-dispatcher-observability/02-VERIFICATION.md` — Phase 2 deliverables confirmed complete; Phase 3 deferred items documented
- `grep -rn "commands/scout-run.md" skills/` — CON-08 dead reference locations verified live as of 2026-04-29

### Secondary (MEDIUM confidence)
- rapidfuzz `token_set_ratio` behavior for suffix stripping — [ASSUMED based on rapidfuzz documentation and training knowledge; not verified via live docs call this session]
- pandas `csv.DictWriter extrasaction="ignore"` behavior — [CITED: Python stdlib docs pattern, consistent with existing codebase use of csv module]

### Tertiary (LOW confidence)
- None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Phase 2 already uses httpx; rapidfuzz was researched 2026-04-27 and locked in PROJECT.md
- Architecture: HIGH — all patterns derived directly from Phase 2 code that is verified and committed
- Pitfalls: HIGH — all derived from concrete code analysis of Phase 2 substrate and locked design decisions
- Test mapping: HIGH — framework and fixture infrastructure already exists from Phases 1/2

**Research date:** 2026-04-29
**Valid until:** Phase 3 execution (code is locked in git; no external API behavior to go stale until Phase 4 adds Lever/Ashby)

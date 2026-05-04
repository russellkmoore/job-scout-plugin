#!/usr/bin/env python3
"""
detect.py — ATS provider detection CLI for Job Scout.

Exposes two subcommands:
  detect-one <company_slug> [--name <display_name>] [--data-dir <data_dir>]
  detect-batch <csv_path> [--limit N] [--force] [--data-dir <data_dir>]

detect-one probes each provider in PROVIDERS registry order, applies the
two-factor gate (HTTP 200 + >=1 job + rapidfuzz name match >=85%), and prints
a JSON result as the LAST stdout line.

detect-batch reads master_targets.csv, runs detect-one logic for each
qualifying row concurrently, writes results back to CSV on the main thread
(D-05: no CSV writes from worker threads), and appends a detection telemetry
line to runs.jsonl.

Concurrency invariants (D-05):
  - Workers: compute DetectionResult objects only
  - Main thread: all CSV writes (_write_back, _append_borderline) happen
    after futures drain, never inside _detect_one_company

Sentinel values (D-01 locked decision):
  - Negative result: ats_provider="none" (NOT "none_detected")
  - Manual lock: ats_provider="manual" — never overwritten regardless of --force

Usage:
    python3 scripts/ats/detect.py detect-one airbnb --name "Airbnb, Inc." --data-dir <data_dir>
    python3 scripts/ats/detect.py detect-batch <data_dir>/master_targets.csv --limit 30 --data-dir <data_dir>
"""

import csv
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
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

from ats import PROVIDERS  # noqa: E402
from ats.providers.base import DetectionResult, DetectionStatus  # noqa: E402
from ats.dispatcher import (  # noqa: E402
    load_caps_and_kill_switch,
    DEFAULT_PROVIDER_CAPS,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
)

# ---------------------------------------------------------------------------
# Module-level constants (locked decisions — do not change without plan update)
# ---------------------------------------------------------------------------

NEG_SENTINEL = "none"       # D-01: REQUIREMENTS.md DET-04 wins over CLAUDE.md draft
MANUAL_LOCK = "manual"      # STR-02/STR-04: never overwritten by detect.py
FRESH_DETECTION_DAYS = 30   # DET-04 idempotency window
NAME_MATCH_HIGH = 85.0      # DET-03 confirmed threshold (>=85 → CONFIRMED)
NAME_MATCH_LOW = 70.0       # DET-03 borderline floor (70–84 → BORDERLINE; <70 → NOT_FOUND)

REVIEW_CSV_FIELDNAMES = [
    "detected_date",
    "company_name",
    "company_slug",
    "provider",
    "name_match_score",
    "ats_board_url",
    "returned_company_name",
    "action",
    "note",
]

# Testability hook: tests can monkeypatch _TODAY_OVERRIDE to pin the date.
# Internal helpers call _get_today() to allow this.
_TODAY_OVERRIDE: Optional[date] = None


def _get_today() -> date:
    """Return today's date. Tests monkeypatch _TODAY_OVERRIDE to pin it."""
    if _TODAY_OVERRIDE is not None:
        return _TODAY_OVERRIDE
    return date.today()


# ---------------------------------------------------------------------------
# Module-level semaphores (separate from dispatcher._SEMAPHORES — A1 in RESEARCH)
# ---------------------------------------------------------------------------

_DET_SEMAPHORES: Dict[str, threading.Semaphore] = {}
_DET_SEMAPHORE_LOCK = threading.Lock()


def _init_detect_semaphores(caps: Dict[str, int]) -> None:
    """Initialize _DET_SEMAPHORES from caps. Mutates in place (clear + update).

    Uses detect-specific semaphores (not dispatcher._SEMAPHORES) to avoid
    cross-starvation when /scout-detect + /scout-run run concurrently (A1).
    """
    with _DET_SEMAPHORE_LOCK:
        _DET_SEMAPHORES.clear()
        _DET_SEMAPHORES.update({p: threading.Semaphore(n) for p, n in caps.items()})


# ---------------------------------------------------------------------------
# Name normalization for rapidfuzz gate
# ---------------------------------------------------------------------------

def _normalize_for_match(name: str) -> str:
    """Lowercase, strip common legal suffixes, strip punctuation.

    'Acme Inc.' -> 'acme'
    'ACME Corp' -> 'acme'
    'The Acme Company LLC' -> 'acme company'

    Handles Unicode via str.casefold() for international company names.
    """
    import re
    name = name.casefold().strip()
    # Strip trailing legal entity suffixes (word-boundary aware)
    name = re.sub(
        r'\b(inc\.?|corp\.?|llc\.?|ltd\.?|co\.?|company|the\b)',
        '',
        name,
    ).strip()
    # Strip punctuation and non-alphanumeric
    name = re.sub(r'[^a-z0-9\s]', '', name)
    return re.sub(r'\s+', ' ', name).strip()


# ---------------------------------------------------------------------------
# Two-factor gate — applies rapidfuzz on top of provider.detect() BORDERLINE
# ---------------------------------------------------------------------------

def _apply_name_gate(
    raw: DetectionResult,
    company_name: str,
    high: float = NAME_MATCH_HIGH,
    low: float = NAME_MATCH_LOW,
) -> DetectionResult:
    """Apply the rapidfuzz name-match half of the two-factor gate (DET-03).

    Called AFTER provider.detect() returns. The provider already checked
    HTTP 200 + >=1 job (factor A). This function applies factor B: the
    company name in the API response must fuzzy-match the input name >=85%.

    Special cases:
      - raw.status in (NOT_FOUND, ERROR): pass through unchanged (no name to match)
      - raw.status == BORDERLINE AND evidence.job_count == 0: D-02 empty-board
        case. Return BORDERLINE preserved with evidence["note"]="zero_open_roles".
        Skip the rapidfuzz step — no first_job_company_name is available.

    Returns a new DetectionResult with:
      - CONFIRMED if score >= high (NAME_MATCH_HIGH=85)
      - BORDERLINE if low <= score < high
      - NOT_FOUND if score < low (but raw was BORDERLINE with jobs)
    """
    if raw.status in (DetectionStatus.NOT_FOUND, DetectionStatus.ERROR):
        return raw  # pass through — no name evidence to score

    # Issue #1: HTTP 200 + zero jobs (SmartRecruiters totalFound=0, Lever empty
    # array, Greenhouse zero-job catch-all) carries no positive signal that this
    # is the right tenant. Without a `first_job_company_name` to fuzzy-match,
    # the two-factor gate has nothing to verify against, so name_match_score=0.0
    # was being silently accepted as a BORDERLINE hit and stamped onto
    # master_targets. Fix: when the empty-board branch can't produce
    # corroborating name evidence, return NOT_FOUND outright.
    #
    # D-02 ("hiring freeze" — empty board for a known-correct tenant) still
    # works as long as the response carries a verifiable name match: that path
    # falls through to the rapidfuzz block below, where score>=high yields
    # CONFIRMED and low<=score<high yields BORDERLINE with the
    # zero_open_roles note.
    returned_name = raw.evidence.get("first_job_company_name", "")
    if raw.evidence.get("job_count", -1) == 0 and not returned_name:
        return DetectionResult(
            provider=raw.provider,
            status=DetectionStatus.NOT_FOUND,
            board_url=None,
            confidence=0.0,
            evidence={
                **raw.evidence,
                "note": "zero_open_roles_no_name_evidence",
                "name_match_score": 0.0,
                "input_name": company_name,
                "returned_name": "",
            },
        )

    # Extract returned company name from evidence dict
    if not returned_name:
        # No company name in response — treat as BORDERLINE with 0 confidence
        # (Greenhouse always includes company_name; absence means wildcard catch-all)
        score = 0.0
    else:
        score = fuzz.token_set_ratio(
            _normalize_for_match(company_name),
            _normalize_for_match(returned_name),
        )

    confidence = score / 100.0

    augmented_evidence = {
        **raw.evidence,
        "name_match_score": score,
        "input_name": company_name,
        "returned_name": returned_name,
    }

    if score >= high:
        return DetectionResult(
            provider=raw.provider,
            status=DetectionStatus.CONFIRMED,
            board_url=raw.board_url,
            confidence=confidence,
            evidence=augmented_evidence,
        )
    elif score >= low:
        return DetectionResult(
            provider=raw.provider,
            status=DetectionStatus.BORDERLINE,
            board_url=raw.board_url,
            confidence=confidence,
            evidence=augmented_evidence,
        )
    else:
        return DetectionResult(
            provider=raw.provider,
            status=DetectionStatus.NOT_FOUND,
            board_url=None,
            confidence=confidence,
            evidence=augmented_evidence,
        )


# ---------------------------------------------------------------------------
# Slug derivation (D-03)
# ---------------------------------------------------------------------------

def _derive_slug(name: str) -> str:
    """D-03 simple normalization. Used when caller passes only --name (no explicit slug).

    'Airbnb' -> 'airbnb'
    'Stripe Inc' -> 'stripe'
    'Lululemon' -> 'lululemon'
    """
    import re
    s = name.lower().replace("'", "")
    # Strip legal suffixes
    for suf in ("inc", "corp", "llc", "ltd", "co", "company", "the"):
        s = re.sub(rf"\b{suf}\b", "", s)
    s = s.replace(" ", "-")
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def _slug_from_board_url(board_url: str) -> Optional[str]:
    """Extract slug from an existing ats_board_url if present.

    e.g. 'https://boards-api.greenhouse.io/v1/boards/airbnb/jobs' -> 'airbnb'
    Returns None if unable to extract.
    """
    import re
    m = re.search(r'/boards/([^/]+)/', board_url)
    if m:
        return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Idempotency skip logic (DET-04)
# ---------------------------------------------------------------------------

def _should_skip(
    row: Dict[str, Any],
    force: bool,
    today: Optional[date] = None,
) -> Tuple[bool, str]:
    """Returns (skip_bool, reason_string). manual lock is absolute.

    Reasons:
      "manual-lock"           — ats_provider=="manual", cannot be overridden
      "fresh-detection:Nd-ago"— non-empty provider, last hit <30d, force=False
      "already-set:<prov>"    — non-empty provider, no last_ats_hit_date, force=False
      ""                      — should NOT skip (detect this row)

    today kwarg: allows tests to pin the date (default: _get_today()).
    """
    if today is None:
        today = _get_today()

    ats_prov = (row.get("ats_provider") or "").strip()

    # Absolute lock: manual is never overwritten, even with --force
    if ats_prov == MANUAL_LOCK:
        return True, "manual-lock"

    # force=True and non-manual: always detect
    if force and ats_prov != MANUAL_LOCK:
        return False, ""

    # No provider yet: always detect
    if not ats_prov:
        return False, ""

    # Provider is set; check freshness (force=False implicit here)
    last_hit = (row.get("last_ats_hit_date") or "").strip()
    if last_hit:
        try:
            delta = (today - date.fromisoformat(last_hit)).days
            if delta < FRESH_DETECTION_DAYS:
                return True, f"fresh-detection:{delta}d-ago"
        except ValueError:
            pass  # malformed date — don't skip

    # Provider set but no last_ats_hit_date (or stale hit >=30d): skip if not forced
    # Wait — if stale (>=30d) we should NOT skip; only skip if fresh or no date
    if last_hit:
        try:
            delta = (today - date.fromisoformat(last_hit)).days
            if delta >= FRESH_DETECTION_DAYS:
                return False, ""  # stale — re-detect
        except ValueError:
            pass
        return False, ""  # invalid date — re-detect

    # No last_ats_hit_date but provider is set: skip (already set, not stale)
    return True, f"already-set:{ats_prov}"


# ---------------------------------------------------------------------------
# Confidence -> CSV column (STR-02)
# ---------------------------------------------------------------------------

def _confidence_to_csv(result: DetectionResult) -> str:
    """Map DetectionResult to the ats_slug_confidence CSV value.

    CONFIRMED  -> str(round(confidence, 4))  e.g. "0.97" (1.0 typical for two-factor pass)
    BORDERLINE -> str(round(confidence, 4))  e.g. "0.78" (0.70-0.94 fuzzy gray band)
                  EXCEPT zero_open_roles edge case (D-02): empty (no job data → no name to score)
    NOT_FOUND  -> ""  (no confidence to store)
    ERROR      -> ""  (detection did not complete)
    manual     -> "manual"  (only written by user; detect.py never writes this)
    """
    if result.status == DetectionStatus.CONFIRMED:
        return str(round(result.confidence, 4))
    if result.status == DetectionStatus.BORDERLINE:
        if result.evidence.get("note") == "zero_open_roles":
            return ""
        return str(round(result.confidence, 4))
    return ""


# ---------------------------------------------------------------------------
# CSV write helpers (D-05 — main thread only)
# ---------------------------------------------------------------------------

def _write_back(
    csv_path: str,
    rows: List[Dict[str, Any]],
    fieldnames: List[str],
) -> None:
    """Write updated rows to master_targets.csv preserving column order.

    fieldnames MUST be derived from the EXISTING CSV header (read before
    any modifications) so user-added columns are preserved at the end.
    Never derive fieldnames from MASTER_TARGETS_COLUMNS alone.

    D-05: only called from _cmd_detect_batch (main thread), never from workers.
    """
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _append_borderline(review_path: str, row: Dict[str, Any]) -> None:
    """Append one borderline row to ats_detection_review.csv.

    Creates the file with header if it doesn't exist. Append-only — never
    reads or rewrites the file. Flushes after each write for durability.

    D-04 (plan): review_path is <data_dir>/ats_detection_review.csv.
    D-05: only called from _cmd_detect_batch (main thread), never from workers.
    """
    file_exists = os.path.isfile(review_path) and os.path.getsize(review_path) > 0
    with open(review_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_CSV_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
        f.flush()


def _append_detection_telemetry(
    runs_log_path: str,
    line_dict: Dict[str, Any],
) -> None:
    """Append ONE detection telemetry line to runs.jsonl.

    Uses the same open-append-flush pattern as runs_log.py (append-only,
    never read or rewrite). Compact JSON (no indent) to keep file scannable.

    DET-07: one line per detect-batch run, never per detect-one.
    D-05: only called from _cmd_detect_batch (main thread).
    """
    with open(runs_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line_dict, ensure_ascii=False, separators=(",", ":")) + "\n")
        f.flush()


# ---------------------------------------------------------------------------
# Worker function (runs in ThreadPoolExecutor)
# ---------------------------------------------------------------------------

def _detect_one_company(
    company_slug: str,
    company_name: str,
    client: "httpx.Client",
    caps: Dict[str, int],
) -> DetectionResult:
    """Probe all PROVIDERS in registry order; return first CONFIRMED result.

    DET-02: stops at first CONFIRMED (registry insertion order, Python 3.7+).
    DET-03: applies _apply_name_gate() on top of each provider.detect() result.

    Exception handling (mirrors dispatcher._execute_one DSP-06 two-tier):
      Tier 1 (re-raise): KeyboardInterrupt, MemoryError, SystemExit
      Tier 2 (bucket as ERROR): every other Exception

    D-05 invariant: this function NEVER writes to CSV or runs.jsonl.
    All side effects happen on the main thread after futures drain.
    """
    t0 = time.monotonic()
    best: Optional[DetectionResult] = None

    # Status priority for best-so-far tracking (CONFIRMED > BORDERLINE > NOT_FOUND > ERROR)
    STATUS_PRIORITY = {
        DetectionStatus.CONFIRMED: 4,
        DetectionStatus.BORDERLINE: 3,
        DetectionStatus.NOT_FOUND: 2,
        DetectionStatus.ERROR: 1,
    }

    for provider_name, provider in PROVIDERS.items():
        # D-3 (locked Phase 4 decision): skip providers with empty
        # BOARD_URL_PATTERNS. jsonld.py has BOARD_URL_PATTERNS=[] — it is
        # a fallback, not a detectable ATS. Probing it would always return
        # NOT_FOUND and waste a network call.
        if not getattr(provider, "BOARD_URL_PATTERNS", None):
            continue
        # Acquire per-provider semaphore (detect-specific, not shared with dispatcher)
        sem = _DET_SEMAPHORES.get(provider_name)
        if sem is None:
            print(
                f"WARNING: no detect semaphore for provider {provider_name!r}; using Semaphore(1)",
                file=sys.stderr,
            )
            sem = threading.Semaphore(1)

        try:
            sem.acquire()
            try:
                raw = provider.detect(company_slug, company_name, client)
            finally:
                sem.release()

            gated = _apply_name_gate(raw, company_name)

            if gated.status == DetectionStatus.CONFIRMED:
                return gated  # DET-02: stop at first CONFIRMED

            # Track best result (for when no provider CONFIRMS)
            if best is None or STATUS_PRIORITY.get(gated.status, 0) > STATUS_PRIORITY.get(best.status, 0):
                best = gated

        except (KeyboardInterrupt, MemoryError, SystemExit):
            raise  # Tier 1: unrecoverable — propagate
        except Exception as exc:  # noqa: BLE001 — Tier 2: recoverable per-fetch failure
            elapsed = time.monotonic() - t0
            err = f"{type(exc).__name__}: {exc}"
            print(f"ERROR: {provider_name}/{company_slug}: {err}", file=sys.stderr)
            error_result = DetectionResult(
                provider="",
                status=DetectionStatus.ERROR,
                board_url=None,
                confidence=0.0,
                evidence={"error": err, "elapsed_seconds": round(elapsed, 3)},
            )
            if best is None or STATUS_PRIORITY.get(error_result.status, 0) > STATUS_PRIORITY.get(best.status, 0):
                best = error_result

    # No provider CONFIRMED: return best (BORDERLINE > NOT_FOUND > ERROR)
    if best is not None:
        return best

    # Synthetic NOT_FOUND if no provider returned anything at all
    return DetectionResult(
        provider="",
        status=DetectionStatus.NOT_FOUND,
        board_url=None,
        confidence=0.0,
        evidence={},
    )


# ---------------------------------------------------------------------------
# detect-one subcommand
# ---------------------------------------------------------------------------

def _cmd_detect_one(args: List[str]) -> None:
    """Implement `detect-one <company_slug> [--name <name>] [--data-dir <dir>]`."""
    if not args or args[0].startswith("-"):
        print(
            "Usage: detect-one <company_slug> [--name <display_name>] [--data-dir <data_dir>]",
            file=sys.stderr,
        )
        sys.exit(1)

    company_slug = args[0]
    company_name = company_slug  # default: use slug as display name
    data_dir: Optional[str] = None

    i = 1
    while i < len(args):
        if args[i] == "--name" and i + 1 < len(args):
            company_name = args[i + 1]
            i += 2
        elif args[i] == "--data-dir" and i + 1 < len(args):
            data_dir = os.path.expanduser(args[i + 1])
            i += 2
        else:
            print(f"ERROR: unknown argument {args[i]!r}", file=sys.stderr)
            sys.exit(1)

    # Load caps from config.json if data_dir provided; else use defaults
    caps = dict(DEFAULT_PROVIDER_CAPS)
    if data_dir:
        config_path = os.path.join(data_dir, "config.json")
        caps, _ = load_caps_and_kill_switch(config_path)

    _init_detect_semaphores(caps)

    # Open ONE httpx.Client (DSP-03 contract: one shared client per run)
    client = httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": DEFAULT_USER_AGENT},
        follow_redirects=True,
    )
    try:
        result = _detect_one_company(company_slug, company_name, client, caps)
    finally:
        client.close()

    # Last stdout line: JSON dict (DET-01 contract)
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


# ---------------------------------------------------------------------------
# detect-batch subcommand
# ---------------------------------------------------------------------------

def _cmd_detect_batch(args: List[str]) -> None:
    """Implement `detect-batch <csv_path> [--limit N] [--force] [--data-dir <dir>]`."""
    if not args or args[0].startswith("-"):
        print(
            "Usage: detect-batch <csv_path> [--limit N] [--force] [--data-dir <data_dir>]",
            file=sys.stderr,
        )
        sys.exit(1)

    csv_path = os.path.expanduser(args[0])
    limit: Optional[int] = None
    force = False
    data_dir: Optional[str] = None

    i = 1
    while i < len(args):
        if args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        elif args[i] == "--force":
            force = True
            i += 1
        elif args[i] == "--data-dir" and i + 1 < len(args):
            data_dir = os.path.expanduser(args[i + 1])
            i += 2
        else:
            print(f"ERROR: unknown argument {args[i]!r}", file=sys.stderr)
            sys.exit(1)

    # Load caps + kill switch
    caps = dict(DEFAULT_PROVIDER_CAPS)
    kill_switch = False
    if data_dir:
        config_path = os.path.join(data_dir, "config.json")
        caps, kill_switch = load_caps_and_kill_switch(config_path)

    _init_detect_semaphores(caps)

    wall_t0 = time.monotonic()
    today = _get_today()

    # Step A: Read CSV on main thread — capture ALL column names (preserving user columns)
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        original_fieldnames: List[str] = list(reader.fieldnames or [])
        all_rows: List[Dict[str, Any]] = [dict(row) for row in reader]

    # Step B: Build task list — determine which rows need detection
    detect_tasks: List[Tuple[int, str, str]] = []  # (row_idx, slug, name)
    skipped_count = 0
    per_company_results: Dict[str, Any] = {}

    for idx, row in enumerate(all_rows):
        company_name = (row.get("company_name") or "").strip()
        if not company_name:
            skipped_count += 1
            continue

        should_skip, reason = _should_skip(row, force, today=today)
        if should_skip:
            skipped_count += 1
            # Include skipped rows in per_company telemetry with skip reason
            slug = _derive_slug(company_name)
            per_company_results[slug] = {
                "provider": row.get("ats_provider", ""),
                "status": "skipped",
                "score": 0.0,
                "reason": reason,
            }
            continue

        # Derive slug from existing ats_board_url if available; else normalize company_name
        existing_url = (row.get("ats_board_url") or "").strip()
        slug = _slug_from_board_url(existing_url) if existing_url else None
        if not slug:
            slug = _derive_slug(company_name)

        detect_tasks.append((idx, slug, company_name))

    # Apply --limit to detection tasks (not to skipped rows)
    if limit is not None:
        detect_tasks = detect_tasks[:limit]

    # Step C: Open ONE httpx.Client + ThreadPoolExecutor
    results_by_idx: Dict[int, DetectionResult] = {}

    if kill_switch:
        # Sequential fallback (ats.concurrency_disabled=true)
        client = httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            follow_redirects=True,
        )
        try:
            for idx, slug, name in detect_tasks:
                results_by_idx[idx] = _detect_one_company(slug, name, client, caps)
        finally:
            client.close()
    else:
        max_workers = max(1, sum(caps.values()))
        client = httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            limits=httpx.Limits(max_connections=max_workers, max_keepalive_connections=max_workers),
            follow_redirects=True,
        )
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_map = {
                    pool.submit(_detect_one_company, slug, name, client, caps): idx
                    for idx, slug, name in detect_tasks
                }
                # Drain futures on main thread
                for fut, idx in future_map.items():
                    results_by_idx[idx] = fut.result()
        finally:
            client.close()

    # Step D: Apply gate results to row dicts ON MAIN THREAD
    confirmed_count = 0
    borderline_count = 0
    not_found_count = 0
    error_count = 0

    borderline_rows_to_append: List[Dict[str, Any]] = []

    for idx, slug, company_name in detect_tasks:
        gated = results_by_idx[idx]
        row = all_rows[idx]

        # Determine if this is a zero-jobs BORDERLINE (D-02)
        is_zero_jobs = (
            gated.status == DetectionStatus.BORDERLINE
            and gated.evidence.get("note") == "zero_open_roles"
        )

        if gated.status == DetectionStatus.CONFIRMED:
            confirmed_count += 1
            row["ats_provider"] = gated.provider
            row["ats_board_url"] = gated.board_url or ""
            row["ats_slug_confidence"] = _confidence_to_csv(gated)
            row["last_ats_hit_date"] = today.isoformat()
            per_company_results[slug] = {
                "provider": gated.provider,
                "status": "CONFIRMED",
                "score": gated.evidence.get("name_match_score", round(gated.confidence * 100, 2)),
            }

        elif gated.status == DetectionStatus.BORDERLINE:
            borderline_count += 1
            # ROADMAP SC-1: write fuzzy score (0.70-0.94) for normal borderline; empty for zero_open_roles (D-02).
            # _confidence_to_csv() handles the discriminator on evidence.note.
            row["ats_provider"] = gated.provider
            row["ats_board_url"] = gated.board_url or ""
            row["ats_slug_confidence"] = _confidence_to_csv(gated)
            # Do NOT set last_ats_hit_date for borderline (no confirmed detection)

            per_company_results[slug] = {
                "provider": gated.provider,
                "status": "BORDERLINE",
                "score": gated.evidence.get("name_match_score", 0.0),
                "zero_open_roles": is_zero_jobs,
            }

            # Prepare review CSV row
            review_row: Dict[str, Any] = {
                "detected_date": today.isoformat(),
                "company_name": company_name,
                "company_slug": slug,
                "provider": gated.provider,
                "name_match_score": gated.evidence.get("name_match_score", 0.0),
                "ats_board_url": gated.board_url or "",
                "returned_company_name": gated.evidence.get("returned_name", ""),
                "action": "",
                "note": "zero_open_roles" if is_zero_jobs else "",
            }
            borderline_rows_to_append.append(review_row)

        elif gated.status in (DetectionStatus.NOT_FOUND, DetectionStatus.ERROR):
            if gated.status == DetectionStatus.NOT_FOUND:
                not_found_count += 1
            else:
                error_count += 1
            # D-01: write NEG_SENTINEL "none" (not "none_detected", not empty)
            row["ats_provider"] = NEG_SENTINEL
            row["ats_slug_confidence"] = ""
            per_company_results[slug] = {
                "provider": gated.provider or NEG_SENTINEL,
                "status": gated.status.value,
                "score": gated.evidence.get("name_match_score", 0.0),
            }

    # Step E: Write CSV back ON MAIN THREAD
    _write_back(csv_path, all_rows, original_fieldnames)

    # Step F: Append review CSV rows ON MAIN THREAD
    if data_dir and borderline_rows_to_append:
        review_path = os.path.join(data_dir, "ats_detection_review.csv")
        for review_row in borderline_rows_to_append:
            _append_borderline(review_path, review_row)

    # Step G: Append ONE detection telemetry line to runs.jsonl ON MAIN THREAD
    wall_clock = time.monotonic() - wall_t0
    if data_dir:
        runs_log_path = os.path.join(data_dir, "runs.jsonl")
        if os.path.exists(runs_log_path):
            detection_line = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "run_type": "detect_batch",
                "wall_clock_seconds": round(wall_clock, 3),
                "companies_total": len(detect_tasks) + skipped_count,
                "confirmed": confirmed_count,
                "borderline": borderline_count,
                "not_found": not_found_count,
                "error": error_count,
                "skipped": skipped_count,
                "per_company": per_company_results,
            }
            _append_detection_telemetry(runs_log_path, detection_line)
        else:
            print(
                f"WARNING: runs.jsonl not found at {runs_log_path}; skipping telemetry",
                file=sys.stderr,
            )
    else:
        print(
            "WARNING: --data-dir not provided; skipping runs.jsonl telemetry append",
            file=sys.stderr,
        )

    # Step H: Print JSON summary as LAST stdout line (DET-01 contract)
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


# ---------------------------------------------------------------------------
# Bottom-of-file CLI dispatcher (DET-01)
# ---------------------------------------------------------------------------

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
        sys.exit(0)
    elif cmd == "detect-batch":
        _cmd_detect_batch(sys.argv[2:])
        sys.exit(0)
    elif cmd in ("--help", "-h"):
        print("detect.py — ATS provider detection\nSubcommands: detect-one, detect-batch")
        sys.exit(0)
    elif cmd == "--version":
        print("detect.py: Phase 3 DET-01..07, v0.4")
        sys.exit(0)
    else:
        print(f"ERROR: unknown command {cmd!r}", file=sys.stderr)
        sys.exit(1)

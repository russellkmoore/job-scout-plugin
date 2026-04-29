"""
runs_log.py — Append-only writer for <data_dir>/runs.jsonl.

DSP-07 (locked Phase 2 decision): exactly one JSON line per /scout-run.
Append-only — opens runs.jsonl in 'a' mode, writes one line, flushes.
NEVER loads + rewrites the entire file (a 365-run file would balloon
/scout-run wall-clock; rotation is a v0.5+ concern per OOS list).

Per-line schema (the trust-on-zero defensibility — PITFALLS.md Pitfall 1):
    {
      "timestamp": "2026-04-28T13:55:00Z",
      "wall_clock_seconds": 234.7,
      "providers": {
        "greenhouse": {
          "ok_with_results": 12,
          "ok_zero": 3,
          "error": 1,
          "field_completion": {
            "company": 1.0, "title": 1.0, "location": 0.97,
            "url": 1.0, "posted_date": 0.94, "source": 1.0
          }
        }
      },
      "per_company_provider": {
        "stripe|greenhouse": {"outcome": "OK_WITH_RESULTS", "listing_count": 5},
        "lululemon|greenhouse": {"outcome": "OK_ZERO", "listing_count": 0}
      }
    }

Without per_company_provider hit counts, "trust ATS on 0/error" silently
zeroes out clusters of companies. With them, Phase 5's ATS-regression-suspect
warnings have something to compare against.

Threat T-02-02 (Information Disclosure): runs.jsonl writes ONLY structured
counts/timings/slugs/provider-names. NEVER raw response bodies, NEVER
resume_path or candidate_profile contents. The schema above is the
contract — additions go through a plan, not an ad-hoc commit.
"""

import json
import os
import sys
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

# Sibling-script bootstrap (2-level — file → ats → scripts). Needed so direct
# script invocation (python3 scripts/ats/runs_log.py) and module-style
# (python3 -m ats.runs_log) both resolve `from ats.normalize` identically.
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
from ats.normalize import REQUIRED_FIELDS, compute_missing_fields  # noqa: E402,F401


class RunOutcome(Enum):
    """Per-(company, provider) 3-state outcome (DSP-05).

    Shared with dispatcher.py — single source of truth lives here so
    runs_log.py's writer schema and dispatcher.py's worker bucketing
    use identical string values. Phase 5's runs.jsonl readers compare
    against `.value` strings.
    """

    OK_WITH_RESULTS = "OK_WITH_RESULTS"
    OK_ZERO = "OK_ZERO"
    ERROR = "ERROR"


def compute_field_completion(listing_dicts: List[Dict[str, Any]]) -> Dict[str, float]:
    """Per-required-field completion rate (% of listings WITH the field non-empty).

    Returns {field_name: 0.0..1.0}. Empty listing_dicts -> all 1.0
    (vacuous truth — no listings can't be missing fields).
    """
    if not listing_dicts:
        return {f: 1.0 for f in REQUIRED_FIELDS}
    n = len(listing_dicts)
    completion: Dict[str, float] = {}
    for fname in REQUIRED_FIELDS:
        present = sum(
            1
            for d in listing_dicts
            if d.get(fname) and (not isinstance(d.get(fname), str) or d.get(fname).strip())
        )
        completion[fname] = round(present / n, 4)
    return completion


def append_run(
    runs_log_path: str,
    wall_clock_seconds: float,
    per_provider_outcomes: Dict[str, Dict[str, int]],
    per_company_provider: Dict[str, Dict[str, Any]],
    per_provider_listings: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Append one JSON line to runs.jsonl.

    Args:
        runs_log_path: absolute path to <data_dir>/runs.jsonl. Caller has
            already expanded `~`. Phase 1 SCH-01 guarantees the file
            exists (validate_runs_log).
        wall_clock_seconds: total /scout-run wall clock (float).
        per_provider_outcomes: {"greenhouse": {"ok_with_results": 12,
            "ok_zero": 3, "error": 1}}. Keys are RunOutcome enum string
            values, values are counts.
        per_company_provider: {"stripe|greenhouse": {"outcome":
            "OK_WITH_RESULTS", "listing_count": 5}}. Compound key uses
            "|" separator (no slug should contain |). Used by Phase 5's
            ATS-regression-suspect detection.
        per_provider_listings: {"greenhouse": [listing_dict, ...]}.
            Used to compute field_completion telemetry per provider.
            Pass listing dicts (Listing.to_dict()), NOT Listing objects.
        timestamp: ISO 8601 (defaults to now()). Override for tests.

    Returns: the JSON-encoded line dict (also written to the file).
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    providers_block: Dict[str, Dict[str, Any]] = {}
    for provider, counts in per_provider_outcomes.items():
        providers_block[provider] = dict(counts)
        if per_provider_listings and provider in per_provider_listings:
            providers_block[provider]["field_completion"] = compute_field_completion(
                per_provider_listings[provider]
            )

    line = {
        "timestamp": timestamp,
        "wall_clock_seconds": round(float(wall_clock_seconds), 3),
        "providers": providers_block,
        "per_company_provider": per_company_provider,
    }

    # Append-only: open in 'a' mode, write the JSON line + newline, flush.
    # Never read the file. Never rewrite. DSP-07 atomicity contract.
    with open(runs_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n")
        f.flush()

    return line


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/ats/runs_log.py <command> [args...]", file=sys.stderr)
        print("Commands:", file=sys.stderr)
        print("  append-run <runs_log_path> <stats.json>", file=sys.stderr)
        print("    stats.json shape: {wall_clock_seconds, per_provider_outcomes,", file=sys.stderr)
        print("                       per_company_provider[, per_provider_listings]}", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "append-run":
        if len(sys.argv) < 4:
            print("Usage: append-run <runs_log_path> <stats.json>", file=sys.stderr)
            sys.exit(1)
        runs_log_path = os.path.expanduser(sys.argv[2])
        stats_path = os.path.expanduser(sys.argv[3])
        with open(stats_path, "r", encoding="utf-8") as f:
            stats = json.load(f)
        line = append_run(
            runs_log_path=runs_log_path,
            wall_clock_seconds=stats["wall_clock_seconds"],
            per_provider_outcomes=stats["per_provider_outcomes"],
            per_company_provider=stats["per_company_provider"],
            per_provider_listings=stats.get("per_provider_listings"),
            timestamp=stats.get("timestamp"),
        )
        print(json.dumps({"appended": True, "line": line}, indent=2))
        sys.exit(0)
    print(f"ERROR: Unknown command: {cmd}", file=sys.stderr)
    sys.exit(1)

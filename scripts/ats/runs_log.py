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
    # Phase 5 D-2 additions — all Optional, non-breaking for existing callers
    dedup_decisions: Optional[List[Dict[str, Any]]] = None,
    regression_suspects: Optional[List[Dict[str, Any]]] = None,
    pass2_board_status: Optional[Dict[str, int]] = None,
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
        dedup_decisions: Phase 5 D-2 — cross-source dedup decisions list.
            Only emitted to line dict when non-None and non-empty.
        regression_suspects: Phase 5 D-2 — list of (company, provider) pairs
            flagged as ATS regression suspects this run.
            Only emitted to line dict when non-None and non-empty.
        pass2_board_status: Phase 5 D-2 — {board_name: result_count} for
            each Pass-2 board queried this run.
            Only emitted to line dict when non-None and non-empty.

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

    # Phase 5 D-2 — only emit non-empty/non-None telemetry keys (back-compat
    # for Phase 2-4 callers that don't pass these kwargs: their JSONL lines are
    # unchanged). Truthiness check: None and [] both False, {} both False.
    if dedup_decisions:
        line["dedup_decisions"] = dedup_decisions
    if regression_suspects:
        line["regression_suspects"] = regression_suspects
    if pass2_board_status:
        line["pass2_board_status"] = pass2_board_status

    # Append-only: open in 'a' mode, write the JSON line + newline, flush.
    # Never read the file. Never rewrite. DSP-07 atomicity contract.
    with open(runs_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n")
        f.flush()

    return line


def _find_regression_suspects(
    lines: List[Dict[str, Any]],
    lookback: int = 5,
    min_prior_ok: int = 3,
) -> List[Dict[str, Any]]:
    """DDP-08 — flag (company, provider) pairs whose CURRENT run shows OK_ZERO/ERROR
    but who showed OK_WITH_RESULTS in at least `min_prior_ok` of the prior `lookback` runs.

    Pitfall 5: prior is lines[-(lookback+1):-1]; current is lines[-1].
    The current run IS already appended to runs.jsonl when this is called from the CLI.
    Incorrect offsets (e.g. lines[-lookback:] inclusive of current) would under-count
    prior OK runs and produce false negatives. Encapsulated here so SKILL.md prose
    never needs to know the arithmetic.

    Args:
        lines: full list of parsed JSONL dicts (all runs including current).
        lookback: how many prior runs to compare against (default 5).
        min_prior_ok: minimum OK_WITH_RESULTS count in prior runs to flag (default 3).

    Returns: [{company_slug, provider, prior_ok_count, current_outcome}, ...]
    """
    if len(lines) < 2:
        return []

    current = lines[-1]
    # Pitfall 5: prior excludes the current run (lines[-1])
    prior = lines[-(lookback + 1):-1] if len(lines) > lookback else lines[:-1]

    current_pcp = current.get("per_company_provider") or {}
    suspects: List[Dict[str, Any]] = []

    for key, info in current_pcp.items():
        current_outcome = info.get("outcome")
        if current_outcome not in ("OK_ZERO", "ERROR"):
            continue

        prior_ok_count = 0
        for prior_run in prior:
            prior_pcp = prior_run.get("per_company_provider") or {}
            prior_info = prior_pcp.get(key)
            if prior_info and prior_info.get("outcome") == "OK_WITH_RESULTS":
                prior_ok_count += 1

        if prior_ok_count >= min_prior_ok:
            # Key format is "company_slug|provider"
            if "|" in key:
                company_slug, provider = key.split("|", 1)
            else:
                company_slug, provider = key, ""
            suspects.append({
                "company_slug": company_slug,
                "provider": provider,
                "prior_ok_count": prior_ok_count,
                "current_outcome": current_outcome,
            })

    return suspects


def _find_pass2_board_broken(
    lines: List[Dict[str, Any]],
    lookback: int = 5,
    min_zero_runs: int = 3,
) -> List[Dict[str, Any]]:
    """CON-15 — flag Pass-2 boards that returned 0 results in >= min_zero_runs of
    the last `lookback` runs (current run included in the window).

    Unlike _find_regression_suspects, the current run IS part of the lookback window
    here (we want to know if today's run continues a pattern, not trigger on current).

    Args:
        lines: full list of parsed JSONL dicts (all runs including current).
        lookback: how many runs (ending with current) to examine (default 5).
        min_zero_runs: minimum zero-result runs to flag a board (default 3).

    Returns: [{board, prior_zero_count}, ...]
    """
    if not lines:
        return []

    recent = lines[-lookback:]
    board_zero_counts: Dict[str, int] = {}

    for run in recent:
        pass2 = run.get("pass2_board_status") or {}
        for board, count in pass2.items():
            try:
                if int(count) == 0:
                    board_zero_counts[board] = board_zero_counts.get(board, 0) + 1
            except (TypeError, ValueError):
                continue

    return [
        {"board": board, "prior_zero_count": cnt}
        for board, cnt in board_zero_counts.items()
        if cnt >= min_zero_runs
    ]


def _cmd_regression_suspects(args: List[str]) -> None:
    """regression-suspects <runs_log_path> [--lookback N] [--min-prior-ok N]

    Reads runs.jsonl, calls _find_regression_suspects, prints JSON to stdout.
    JSON is the LAST print per CONVENTIONS.md (machine-consumable as final line).
    """
    if not args:
        print(
            "Usage: runs_log.py regression-suspects <runs_log_path> [--lookback N] [--min-prior-ok N]",
            file=sys.stderr,
        )
        sys.exit(1)

    runs_log_path = os.path.expanduser(args[0])
    lookback = 5
    if "--lookback" in args:
        lookback = int(args[args.index("--lookback") + 1])
    min_prior_ok = 3
    if "--min-prior-ok" in args:
        min_prior_ok = int(args[args.index("--min-prior-ok") + 1])

    if not os.path.isfile(runs_log_path):
        print(json.dumps([]))
        return

    with open(runs_log_path, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]

    suspects = _find_regression_suspects(lines, lookback=lookback, min_prior_ok=min_prior_ok)
    print(json.dumps(suspects, indent=2))


def _cmd_pass2_board_broken(args: List[str]) -> None:
    """pass2-board-broken <runs_log_path> [--lookback N] [--min-zero-runs N]

    Reads runs.jsonl, calls _find_pass2_board_broken, prints JSON to stdout.
    JSON is the LAST print per CONVENTIONS.md (machine-consumable as final line).
    """
    if not args:
        print(
            "Usage: runs_log.py pass2-board-broken <runs_log_path> [--lookback N] [--min-zero-runs N]",
            file=sys.stderr,
        )
        sys.exit(1)

    runs_log_path = os.path.expanduser(args[0])
    lookback = 5
    if "--lookback" in args:
        lookback = int(args[args.index("--lookback") + 1])
    min_zero_runs = 3
    if "--min-zero-runs" in args:
        min_zero_runs = int(args[args.index("--min-zero-runs") + 1])

    if not os.path.isfile(runs_log_path):
        print(json.dumps([]))
        return

    with open(runs_log_path, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]

    broken = _find_pass2_board_broken(lines, lookback=lookback, min_zero_runs=min_zero_runs)
    print(json.dumps(broken, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/ats/runs_log.py <command> [args...]", file=sys.stderr)
        print("Commands:", file=sys.stderr)
        print("  append-run <runs_log_path> <stats.json>", file=sys.stderr)
        print("    stats.json shape: {wall_clock_seconds, per_provider_outcomes,", file=sys.stderr)
        print("                       per_company_provider[, per_provider_listings,", file=sys.stderr)
        print("                        dedup_decisions, regression_suspects, pass2_board_status]}", file=sys.stderr)
        print("  regression-suspects <runs_log_path> [--lookback N] [--min-prior-ok N]", file=sys.stderr)
        print("  pass2-board-broken <runs_log_path> [--lookback N] [--min-zero-runs N]", file=sys.stderr)
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
            # Phase 5 D-2 passthrough — present in stats.json when SKILL.md passes them
            dedup_decisions=stats.get("dedup_decisions"),
            regression_suspects=stats.get("regression_suspects"),
            pass2_board_status=stats.get("pass2_board_status"),
        )
        print(json.dumps({"appended": True, "line": line}, indent=2))
        sys.exit(0)
    elif cmd == "regression-suspects":
        _cmd_regression_suspects(sys.argv[2:])
        sys.exit(0)
    elif cmd == "pass2-board-broken":
        _cmd_pass2_board_broken(sys.argv[2:])
        sys.exit(0)
    print(f"ERROR: Unknown command: {cmd}", file=sys.stderr)
    sys.exit(1)

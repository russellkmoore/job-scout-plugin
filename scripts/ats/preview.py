"""
preview.py — Phase 2 [ATS-PREVIEW] driver. ONE process invocation per /scout-run.

Why a separate driver script and not three SKILL bash steps?

DSP-03 (locked Phase 2 decision): exactly ONE shared httpx.Client per /scout-run.
The dispatcher's fetch_all owns that Client's lifetime via `with httpx.Client(...)`.
If the SKILL prompt called the dispatcher three times (once for the dispatcher CLI,
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
  2. Call dispatcher.fetch_all with targets + config_path ONCE.
     (fetch_all owns the httpx.Client; instantiated once, closed in `finally`.)
  3. For every OK_WITH_RESULTS outcome, persist its raw payload to
     <data_dir>/daily/<TODAY>/ats_raw/<provider>/<slug>.json.
  4. Aggregate outcomes via dispatcher.aggregate_outcomes.
  5. Append ONE runs.jsonl line via runs_log.append_run with the
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

# Sibling-script bootstrap (2-level — file → ats → scripts; matches
# dispatcher.py / runs_log.py from Plan 02-01).
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

# Imports from sibling modules within the ats package. dispatcher.py
# already handles the httpx ImportError block — preview.py inherits that
# error reporting by importing fetch_all (which lives in dispatcher.py).
from ats.dispatcher import fetch_all, aggregate_outcomes  # noqa: E402
from ats.normalize import apply_filters  # noqa: E402  # PRV-06/07/08, STR-03
from ats.runs_log import append_run, RunOutcome  # noqa: E402


def run_preview(
    data_dir: str,
    today: str,
    slugs: List[str],
    provider: str = "greenhouse",
    targets: List[Tuple[str, str]] = None,
) -> Dict[str, Any]:
    """Run a single Phase 4 [ATS-PREVIEW] cycle and return the summary dict.

    Args:
        data_dir: absolute path; caller has already expanded ~.
        today:    ISO date string (e.g. "2026-04-28") — already validated by SKILL.
        slugs:    list of company slugs (LEGACY — only when targets is None).
                  Used with `provider` arg for backward compat.
        provider: provider name to use with `slugs` (LEGACY — default greenhouse).
        targets:  list of (slug, provider) tuples — preferred multi-provider input.
                  When provided, slugs+provider are ignored.

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
    # Prefer the explicit `targets` arg when provided (multi-provider routing).
    # Fall back to legacy slugs+provider when targets is None (Phase 2 callers).
    if targets is None:
        targets = [(slug, provider) for slug in slugs if slug]

    # ONE fetch_all call. fetch_all instantiates and closes the httpx.Client
    # internally (DSP-03). We measure wall-clock around THIS line — that's
    # what runs.jsonl reflects.
    t0 = time.monotonic()
    outcomes = fetch_all(targets, config_path)
    wall_clock = time.monotonic() - t0

    # PRV-06 / PRV-07 / PRV-08 / STR-03: post-fetch filtering.
    # Drops stale (>60d default; per-provider overridable), collapses
    # intra-source regional duplicates, removes evergreen titles. Mutates
    # only OK_WITH_RESULTS outcomes; OK_ZERO and ERROR pass through.
    # Load ats config — fall back to apply_filters defaults on read failure.
    ats_cfg: Dict[str, Any] = {}
    try:
        with open(config_path, "r", encoding="utf-8") as _cf:
            ats_cfg = json.load(_cf).get("ats", {}) or {}
    except (OSError, json.JSONDecodeError):
        pass  # apply_filters uses sensible defaults
    outcomes = apply_filters(outcomes, config=ats_cfg)

    # Persist raw payloads from the SAME (now filtered) outcomes.
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


if __name__ == "__main__":
    # --help / --version smoke flags (verify-time sanity)
    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help"):
        print(
            "Usage: python3 scripts/ats/preview.py <data_dir> <TODAY> <targets_csv>\n"
            "\n"
            "Run a single [ATS-PREVIEW] cycle for /scout-run Step 2.5.\n"
            "ONE process -> ONE fetch_all -> ONE httpx.Client -> ONE runs.jsonl append.\n"
            "\n"
            "Args:\n"
            "  <data_dir>     absolute path to user's data dir (~ already expanded by caller).\n"
            "  <TODAY>        ISO date string for today's run (e.g. 2026-04-28).\n"
            "  <targets_csv>  comma-separated targets. Each entry is `slug|provider`\n"
            "                 (e.g. `airbnb|greenhouse,spotify|lever,visa|smartrecruiters`).\n"
            "                 Bare `slug` (no pipe) defaults to provider=greenhouse for\n"
            "                 Phase 2 backward compat. Empty string is OK -- runs the\n"
            "                 empty-targets path (still appends 0-outcome runs.jsonl line).\n"
        )
        sys.exit(0)
    if len(sys.argv) >= 2 and sys.argv[1] == "--version":
        print("preview.py: Phase 4 multi-provider driver, v0.4")
        sys.exit(0)

    if len(sys.argv) < 4:
        print(
            "Usage: python3 scripts/ats/preview.py <data_dir> <TODAY> <targets_csv>",
            file=sys.stderr,
        )
        sys.exit(1)

    data_dir = os.path.expanduser(sys.argv[1])
    today = sys.argv[2]
    targets_csv = sys.argv[3]
    targets: List[Tuple[str, str]] = []
    for entry in targets_csv.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "|" in entry:
            slug, prov = entry.split("|", 1)
            slug = slug.strip()
            prov = prov.strip() or "greenhouse"
            if slug:
                targets.append((slug, prov))
        else:
            # Bare slug — Phase 2 backward compat (greenhouse default)
            targets.append((entry, "greenhouse"))

    try:
        summary = run_preview(data_dir, today, slugs=[], targets=targets)
    except FileNotFoundError:
        sys.exit(2)

    # Drop the runs_jsonl_line from the printed summary -- it's the same
    # info structure but the line is large, and the SKILL only needs the
    # aggregates + raw-persisted manifest.
    printable = {k: v for k, v in summary.items() if k != "runs_jsonl_line"}
    print(json.dumps(printable, indent=2, ensure_ascii=False))
    sys.exit(0)

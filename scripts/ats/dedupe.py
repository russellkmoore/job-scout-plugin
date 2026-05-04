"""dedupe.py — Cross-source dedup for Job Scout Pass 1 (ATS) vs Pass 2/3 (LinkedIn).

Two-key tiered fuzzy dedup using rapidfuzz.token_set_ratio:
  - DDP-01: per-company-slug match
  - DDP-02: tiered confidence band (≥95 auto-merge, 70–94 review, <70 keep both)
  - DDP-03: two-key gate (BOTH loose AND tight must pass auto-merge threshold)
  - DDP-04: decisions[] array for runs.jsonl telemetry
  - DDP-05: helper compute_ats_tier_bump() for +1 tier bump on fresh ATS listings

Locked decisions:
  D-1: Enrichment scope = pre-bump A-tier (any base score reaching A after +1 ATS bump)
  D-3: LinkedIn slug derived at runtime from company_name (no schema column)

Pitfall 3 (locked): _normalize_title is imported from ats.normalize, NEVER copy-pasted.

Usage:
    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/dedupe.py \\
      cross-source \\
      <ats_raw_dir> <linkedin_candidates_path> <output_dedup_result_path> \\
      [--config <data_dir>/config.json]
"""

import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Two-level bootstrap: file -> ats -> scripts
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from ats.normalize import _normalize_title  # Pitfall 3 — IMPORT, never copy

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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_AUTO_MERGE_THRESHOLD = 95
DEFAULT_REVIEW_BAND_MIN = 70
ATS_TIER_BUMP_MAX_AGE_DAYS = 30

# Suffix list for derive_linkedin_slug() — per test_linkedin_slug_runtime spec:
#   "Acme Corp" → "acme-corp" (Corp NOT stripped)
#   "Stripe, Inc." → "stripe" (, Inc. stripped)
#   "Foo LLC" → "foo" ( LLC stripped — note: space, no comma)
#   "Bar Corporation" → "bar-corporation" (Corporation NOT stripped)
LINKEDIN_SUFFIX_PATTERNS = [", Inc.", ", LLC", " LLC"]


# ---------------------------------------------------------------------------
# Key helpers (Pitfall 3: _normalize_title is imported above, never redefined)
# ---------------------------------------------------------------------------

def _loose_key(slug: str, title: str) -> str:
    """slug + '|' + first 3 normalized tokens of title."""
    tokens = _normalize_title(title).split()
    return slug + "|" + " ".join(tokens[:3])


def _tight_key(slug: str, title: str) -> str:
    """slug + '|' + full normalized title."""
    return slug + "|" + _normalize_title(title)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def derive_linkedin_slug(company_name: str) -> str:
    """Derive a LinkedIn URL slug from a company display name. D-3 — no schema column.

    Strips common suffixes (, Inc. / , LLC / _space_LLC), lowercases,
    replaces spaces with dashes, removes non-alphanumeric except dashes.

    Examples:
        "Acme Corp"       → "acme-corp"  (Corp is NOT stripped per spec)
        "Stripe, Inc."    → "stripe"     (strips ', Inc.')
        "Foo LLC"         → "foo"        (strips ' LLC')
        "Bar Corporation" → "bar-corporation"  (Corporation NOT stripped)
    """
    if not company_name:
        return ""
    name = str(company_name).strip()
    for suffix in LINKEDIN_SUFFIX_PATTERNS:
        if name.endswith(suffix):
            name = name[: -len(suffix)].rstrip()
            break  # only strip one suffix
    name = name.lower()
    # Replace whitespace runs with dashes; strip non-alphanumeric except dashes
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"[^a-z0-9\-]", "", name)
    return name.strip("-")


def compute_ats_tier_bump(listing: dict, today: date) -> int:
    """DDP-05 — +1 tier bump iff source startswith 'ats:' AND posted_date <= 30 days ago.

    'Tier bump' here is a flag (0 or 1) — SKILL.md Step 5 interprets 1 as a tier
    elevation (B→A, C→B; A stays A). NOT a raw score addition.
    """
    src = (listing.get("source") or "").lower()
    if not src.startswith("ats:"):
        return 0
    posted = listing.get("posted_date")
    if not posted:
        return 0
    try:
        posted_dt = date.fromisoformat(str(posted)[:10])
    except (ValueError, TypeError):
        return 0
    age_days = (today - posted_dt).days
    if age_days < 0 or age_days > ATS_TIER_BUMP_MAX_AGE_DAYS:
        return 0
    return 1


def is_enrichment_candidate(
    listing: dict,
    base_score: int,
    today: date,
    b_threshold: int = 70,
    a_threshold: int = 76,
) -> bool:
    """D-1 — pre-bump A-tier scope. Returns True iff enriching this listing could
    surface warm-path signal that changes its final tier to A or above.

    Logic: an ATS listing is an enrichment candidate when
        base_score + compute_ats_tier_bump(listing, today) >= a_threshold

    The +1 bump is treated as +1 score point for the candidacy check —
    this is the "pre-bump scope" that avoids enriching after tier assignment.

    Non-ATS listings (source not startswith 'ats:') are always False — D-1 is
    ATS-only. LinkedIn listings get their warm-path signal from the dedup merge.

    Parameters
    ----------
    listing    : dict with at minimum 'source' and 'posted_date' keys
    base_score : numeric score from the 5-category rubric (before any bump)
    today      : date.today() — passed explicitly for testability
    b_threshold: minimum score to be considered B-tier (informational; used by
                 callers to set candidate scope)
    a_threshold: minimum score to qualify as A-tier; default 76 so that
                 base_score=75 + bump=1 = 76 >= 76 → True (matches config
                 tier_a_threshold=75 + 1 bump)
    """
    src = (listing.get("source") or "").lower()
    if not src.startswith("ats:"):
        return False
    bump = compute_ats_tier_bump(listing, today)
    return (base_score + bump) >= a_threshold


# ---------------------------------------------------------------------------
# Internal slug helper
# ---------------------------------------------------------------------------

def _slug_from_listing(listing: dict) -> str:
    """Best-effort slug from a listing dict. Prefer explicit company_slug, else derive."""
    if listing.get("company_slug"):
        return str(listing["company_slug"]).lower()
    return derive_linkedin_slug(listing.get("company", ""))


# ---------------------------------------------------------------------------
# Main dedup function
# ---------------------------------------------------------------------------

def run_cross_source_dedup(
    ats_listings: List[dict],
    linkedin_listings: List[dict],
    config: Optional[dict] = None,
) -> dict:
    """DDP-01/02/03/04 — two-key tiered fuzzy dedup of LinkedIn vs ATS listings.

    Auto-merge condition (DDP-03): BOTH loose_score >= auto_merge_threshold
                                   AND tight_score >= auto_merge_threshold.
    Either alone → review_band.
    Both below review_band_min → keep_both.

    Merge behavior on auto_merge: ATS listing is primary. LinkedIn fields
    (e.g. connection_count, salary_range) are overlaid only when ATS field is
    empty/None. Source stays 'ats:<provider>' (ATS is canonical).

    Returns
    -------
    {
        "merged": [<dict>, ...],        # auto-merged listings (ATS primary)
        "review_band": [<dict>, ...],   # pairs flagged for human review
        "linkedin_only": [<dict>, ...], # LinkedIn listings with no ATS match
        "ats_only": [<dict>, ...],      # ATS listings with no LinkedIn match
        "decisions": [
            {"action": "auto_merge"|"review_band"|"keep_both",
             "ats_url": "...", "linkedin_url": "...",
             "loose_score": int, "tight_score": int,
             "company_slug": "..."},
            ...
        ]
    }
    """
    cfg = (config or {}).get("dedup", {}).get("thresholds", {})
    auto_merge = int(cfg.get("auto_merge", DEFAULT_AUTO_MERGE_THRESHOLD))
    review_min = int(cfg.get("review_band_min", DEFAULT_REVIEW_BAND_MIN))

    # DDP-01: group ATS listings by company_slug for per-slug scoping
    ats_by_slug: Dict[str, List[dict]] = {}
    for a in ats_listings:
        slug = _slug_from_listing(a)
        ats_by_slug.setdefault(slug, []).append(a)

    merged: List[dict] = []
    review_band: List[dict] = []
    linkedin_only: List[dict] = []
    matched_ats_urls: set = set()
    decisions: List[dict] = []

    for li in linkedin_listings:
        li_slug = _slug_from_listing(li)
        candidates = ats_by_slug.get(li_slug, [])

        # Find best-scoring ATS candidate for this LinkedIn listing
        best: Optional[Tuple[dict, int, int]] = None  # (ats_listing, loose_score, tight_score)
        for a in candidates:
            ls = int(fuzz.token_set_ratio(
                _loose_key(li_slug, li.get("title", "")),
                _loose_key(li_slug, a.get("title", "")),
            ))
            ts = int(fuzz.token_set_ratio(
                _tight_key(li_slug, li.get("title", "")),
                _tight_key(li_slug, a.get("title", "")),
            ))
            if best is None or max(ls, ts) > max(best[1], best[2]):
                best = (a, ls, ts)

        if best is None:
            # No ATS candidates for this slug → LinkedIn only
            linkedin_only.append(li)
            continue

        a_match, loose_score, tight_score = best

        # DDP-02/03: two-key gate
        if loose_score >= auto_merge and tight_score >= auto_merge:
            # Auto-merge: ATS is primary; overlay LinkedIn-only fields
            merged_listing = dict(a_match)
            for k, v in li.items():
                if not merged_listing.get(k) and v:
                    merged_listing[k] = v
            # Canonical source stays ATS
            merged_listing["source"] = a_match.get("source", "ats:unknown")
            merged.append(merged_listing)
            matched_ats_urls.add(a_match.get("url"))
            decisions.append({
                "action": "auto_merge",
                "ats_url": a_match.get("url"),
                "linkedin_url": li.get("url"),
                "loose_score": loose_score,
                "tight_score": tight_score,
                "company_slug": li_slug,
            })

        elif max(loose_score, tight_score) >= review_min:
            # One key agrees but not both → review band
            review_band.append({
                "ats": a_match,
                "linkedin": li,
                "loose_score": loose_score,
                "tight_score": tight_score,
            })
            # LinkedIn listing also goes through separately — pending review
            linkedin_only.append(li)
            decisions.append({
                "action": "review_band",
                "ats_url": a_match.get("url"),
                "linkedin_url": li.get("url"),
                "loose_score": loose_score,
                "tight_score": tight_score,
                "company_slug": li_slug,
            })

        else:
            # Both keys below review_min → keep both, no merge
            linkedin_only.append(li)
            decisions.append({
                "action": "keep_both",
                "ats_url": a_match.get("url"),
                "linkedin_url": li.get("url"),
                "loose_score": loose_score,
                "tight_score": tight_score,
                "company_slug": li_slug,
            })

    # ATS listings with no matched LinkedIn counterpart
    ats_only = [a for a in ats_listings if a.get("url") not in matched_ats_urls]

    return {
        "merged": merged,
        "review_band": review_band,
        "linkedin_only": linkedin_only,
        "ats_only": ats_only,
        "decisions": decisions,
    }


# ---------------------------------------------------------------------------
# CLI subcommand: cross-source
# ---------------------------------------------------------------------------

def _cmd_cross_source(args: List[str]) -> None:
    """cross-source <ats_raw_dir> <linkedin_path> <output_path> [--config <path>]

    Reads:
      - <ats_raw_dir>: directory of <provider>/<slug>.json payloads (preview.py shape)
      - <linkedin_path>: JSON file with array of LinkedIn-source Listing dicts
      - --config: optional config.json with dedup.thresholds section

    Writes:
      - <output_path>: dedup_result.json (per-run intermediate)
      - stdout: machine-consumable JSON summary (last print) per CONVENTIONS.md
    """
    if len(args) < 3:
        print(
            "Usage: dedupe.py cross-source <ats_raw_dir> <linkedin_path> <output_path>"
            " [--config <path>]",
            file=sys.stderr,
        )
        sys.exit(1)

    ats_raw_dir = os.path.expanduser(args[0])
    linkedin_path = os.path.expanduser(args[1])
    output_path = os.path.expanduser(args[2])
    config_path = None
    if "--config" in args:
        idx = args.index("--config")
        if idx + 1 < len(args):
            config_path = os.path.expanduser(args[idx + 1])

    # Load ATS listings from per-provider/<slug>.json files (preview.py shape)
    ats_listings: List[dict] = []
    if os.path.isdir(ats_raw_dir):
        for provider_entry in sorted(os.listdir(ats_raw_dir)):
            provider_dir = os.path.join(ats_raw_dir, provider_entry)
            if not os.path.isdir(provider_dir):
                continue
            for fname in sorted(os.listdir(provider_dir)):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(provider_dir, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        payload = json.loads(f.read())
                except (json.JSONDecodeError, OSError) as e:
                    print(f"WARNING: skipping {fname}: {e}", file=sys.stderr)
                    continue
                slug = payload.get("company_slug")
                for listing in payload.get("listings", []):
                    if slug and not listing.get("company_slug"):
                        listing["company_slug"] = slug
                    ats_listings.append(listing)

    # Load LinkedIn candidates
    try:
        with open(linkedin_path, encoding="utf-8") as f:
            linkedin_listings = json.loads(f.read())
    except (json.JSONDecodeError, OSError) as e:
        print(f"ERROR: cannot read linkedin candidates from {linkedin_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Load config if provided
    config: Optional[dict] = None
    if config_path:
        try:
            with open(config_path, encoding="utf-8") as f:
                config = json.loads(f.read())
        except (json.JSONDecodeError, OSError) as e:
            print(f"WARNING: config unreadable, using defaults: {e}", file=sys.stderr)

    # Run dedup
    result = run_cross_source_dedup(ats_listings, linkedin_listings, config)

    # Write result file
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Human-readable progress (stderr, before final JSON)
    print(
        f"Processed {len(ats_listings)} ATS listings + {len(linkedin_listings)} LinkedIn candidates",
        file=sys.stderr,
    )

    # Machine-consumable JSON as the LAST stdout print (CONVENTIONS.md)
    summary = {
        "ok": True,
        "merged": len(result["merged"]),
        "review_band": len(result["review_band"]),
        "ats_only": len(result["ats_only"]),
        "linkedin_only": len(result["linkedin_only"]),
        "decisions": len(result["decisions"]),
    }
    print(json.dumps(summary, indent=2))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/ats/dedupe.py <command> [args...]", file=sys.stderr)
        print("Commands: cross-source", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "cross-source":
        _cmd_cross_source(sys.argv[2:])
        sys.exit(0)
    elif cmd in ("--help", "-h"):
        print("dedupe.py — Cross-source dedup\nCommands: cross-source")
        sys.exit(0)
    elif cmd in ("--version", "-V"):
        print("dedupe.py 0.4.2")
        sys.exit(0)
    else:
        print(f"ERROR: unknown command {cmd!r}", file=sys.stderr)
        sys.exit(1)

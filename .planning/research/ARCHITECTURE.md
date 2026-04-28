# Architecture Research

**Domain:** ATS-first sourcing layer inside an existing Claude Code plugin (skill-orchestrated, script-deterministic)
**Researched:** 2026-04-27
**Confidence:** HIGH (existing patterns are well-mapped; ATS endpoints are publicly documented; the only LOW-confidence area is per-provider concurrency tuning which is intentionally deferred per PROJECT.md)

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  Skill Layer (markdown — orchestration + LLM judgement)              │
├──────────────────────────────────────────────────────────────────────┤
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐    │
│   │ scout-detect │   │  scout-run   │   │  scout-setup (existing)│  │
│   │   (NEW)      │   │  (modified)  │   │   (lightly modified) │    │
│   └──────┬───────┘   └──────┬───────┘   └──────────┬───────────┘    │
│          │                  │                       │                │
│          │   ┌──────────────────────────────────┐   │                │
│          │   │ references/ats-providers.md (NEW)│   │                │
│          │   │ references/search-config.md (mod)│   │                │
│          │   └──────────────────────────────────┘   │                │
├──────────┴──────────────────┴───────────────────────┴────────────────┤
│  Script Layer (Python — deterministic adapters + dispatch)           │
├──────────────────────────────────────────────────────────────────────┤
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │  scripts/ats/                                          (NEW) │   │
│   │  ├── __init__.py                                             │   │
│   │  ├── detect.py        # provider detection (URL → provider)  │   │
│   │  ├── dispatcher.py    # concurrent fetch w/ per-provider cap │   │
│   │  ├── normalize.py     # provider JSON → canonical Listing    │   │
│   │  ├── dedupe.py        # cross-pass dedupe (slug+title fuzzy) │   │
│   │  └── providers/                                              │   │
│   │      ├── __init__.py  # PROVIDERS registry                   │   │
│   │      ├── base.py      # Provider protocol/ABC                │   │
│   │      ├── greenhouse.py│   │
│   │      ├── lever.py     │   │
│   │      ├── ashby.py     │   │
│   │      ├── smartrecruiters.py                                  │   │
│   │      └── workday.py   │   │
│   └──────────────────────────────────────────────────────────────┘   │
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │  Existing scripts (unchanged unless noted)                   │   │
│   │  schema.py | state.py | validate_data.py (mod) |             │   │
│   │  tracker_utils.py | mine_connections.py | consolidate_targets│   │
│   └──────────────────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────────────────┤
│  Data Layer (user-owned, outside plugin)                             │
├──────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────┐  ┌──────────────────────────────────┐   │
│  │ master_targets.csv     │  │ daily/<DATE>/                    │   │
│  │  + ats_provider        │  │  ├── report.md                   │   │
│  │  + ats_board_url       │  │  ├── new_rows.json               │   │
│  │  (already in schema)   │  │  ├── run_log.json                │   │
│  │                        │  │  └── ats_raw/<provider>.json (NEW)│  │
│  └────────────────────────┘  ├──────────────────────────────────┤   │
│                              │ runs.jsonl (NEW, append-only)    │   │
│                              └──────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Lives in |
|-----------|----------------|----------|
| `scout-detect` skill | Orchestrate batch detection across top-30 (or user-supplied subset). LLM judgement: pick the right candidate URL when career page redirects ambiguously, decide when to give up. | `skills/scout-detect/SKILL.md` (NEW) |
| `scout-run` skill | Orchestrate Pass 1 → Pass 2 → enrich → score → write. LLM judgement: scoring, narrative, on-the-fly inline detect for unknown companies. | `skills/scout-run/SKILL.md` (modified) |
| `scripts/ats/detect.py` | Deterministic: given a `career_page_url` (and optional company name), HEAD/GET, sniff response shape, return `(provider, board_url)` or `(unknown, None)`. Pure function over URL + HTTP responses. | NEW |
| `scripts/ats/dispatcher.py` | Deterministic: given a list of `(company, provider, board_url)`, fetch concurrently with per-provider semaphores, return a flat list of normalized `Listing` dicts plus per-provider stats. | NEW |
| `scripts/ats/normalize.py` | Deterministic: provider-specific JSON → canonical `Listing` schema (one shape for all providers). Owns the `Listing` TypedDict / dataclass. | NEW |
| `scripts/ats/dedupe.py` | Deterministic: given Pass 1 listings + Pass 2 listings, return Pass 2 minus anything that fuzzy-matches a Pass 1 row by `(normalize_company_name, normalize_title)`. | NEW |
| `scripts/ats/providers/<name>.py` | One file per ATS. Each exports `BOARD_URL_PATTERNS`, `detect(url, html) -> bool`, `board_url_from_company(company) -> str | None`, `fetch(board_url) -> list[dict]`, `to_listing(raw) -> Listing`. | NEW |
| `scripts/validate_data.py` | Existing role + new responsibility: ensure `ats_provider` and `ats_board_url` columns exist (already covered by the auto-add migration), ensure `daily/ats_raw/` parent exists, ensure `runs.jsonl` is touchable. | MODIFIED |
| `references/ats-providers.md` | Skill-readable knowledge: which providers we support, their URL patterns (so prompts can recognize them in conversation), known quirks (Workday tenant slugs, Lever job-as-page-vs-API gotchas). NOT used by scripts — scripts get the same info from the providers/ modules. | NEW |
| `references/search-config.md` | Existing role + rewrite: replace 3-pass budget with 2-pass + enrich. New share targets (Pass 1 ≥60% of A/B-tier). | MODIFIED |

---

## Recommended Project Structure

```
job-scout-plugin/
├── .claude-plugin/
│   └── plugin.json                              # bump to 0.4.0
├── skills/
│   ├── scout-setup/
│   │   └── SKILL.md                             # +1 line: suggest /scout-detect after setup
│   ├── scout-run/
│   │   └── SKILL.md                             # major rewrite — see Data Flow below
│   ├── scout-detect/                            # NEW SKILL
│   │   └── SKILL.md                             # batch detect for top-N companies
│   └── job-scout/
│       ├── SKILL.md                             # +1 link to ats-providers.md
│       └── references/
│           ├── file-contract.md                 # +entries for ats_raw/ and runs.jsonl
│           ├── search-config.md                 # rewritten for 2-pass + enrich
│           ├── scoring-rubric.md                # +"+1 tier bump for ATS-sourced" section
│           ├── job-boards.md                    # unchanged (Pass 2 still uses these)
│           ├── ats-providers.md                 # NEW: provider matrix, URL patterns, gotchas
│           ├── tailoring-guide.md               # unchanged
│           ├── assessment-framework.md          # unchanged
│           ├── profile-extraction-guide.md      # unchanged
│           └── chrome-setup.md                  # trim: career-page section deleted
├── scripts/
│   ├── schema.py                                # already has ats_provider/ats_board_url
│   ├── state.py                                 # unchanged
│   ├── validate_data.py                         # +ensure ats_raw/ + runs.jsonl
│   ├── tracker_utils.py                         # +source/ats_provider columns? See Schema Note
│   ├── mine_connections.py                     # unchanged
│   ├── consolidate_targets.py                   # unchanged
│   └── ats/                                     # NEW PACKAGE
│       ├── __init__.py                          # re-exports detect_company, fetch_all
│       ├── detect.py                            # CLI: detect-one, detect-batch
│       ├── dispatcher.py                        # CLI: fetch-all
│       ├── normalize.py                         # library only — no CLI
│       ├── dedupe.py                            # CLI: dedupe-pass2
│       ├── runs_log.py                          # CLI: append-run (writes runs.jsonl)
│       └── providers/
│           ├── __init__.py                      # PROVIDERS = {"greenhouse": ..., ...}
│           ├── base.py                          # Provider protocol + Listing dataclass
│           ├── greenhouse.py
│           ├── lever.py
│           ├── ashby.py
│           ├── smartrecruiters.py
│           └── workday.py
├── templates/
│   ├── config.json                              # +search.ats: {concurrency_per_provider, ...}
│   └── candidate_profile.json                   # unchanged
└── README.md                                    # update versioning table
```

### Structure Rationale

- **Why a `scripts/ats/` package, not flat files in `scripts/`.** Existing `scripts/` is a flat directory of ~6 modules. ATS work introduces ~12 files (5 providers + 5 dispatcher/normalize/dedupe/detect/runs + base + `__init__`). A flat layout would dominate the directory and bury the existing scripts. A package is the smallest deviation from current convention that contains the new surface area. The sibling-script bootstrap (`SCRIPTS_DIR` / `sys.path.insert`) still works because `scripts/ats/__init__.py` can re-export everything the CLIs need, and inside the package `from ..schema import ...` works after the same bootstrap (or `from schema import ...` if the CLI lives at `scripts/ats/<x>.py` and runs the bootstrap itself). Keep CLIs at the package's top-level files (`scripts/ats/detect.py`, etc.) so prompts can call `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/detect.py ...` with the same shape they use today.

- **Why a `providers/` subpackage.** Five providers with substantially different payload shapes, board URL conventions, and quirks. Concerns from the codebase mapping called out: *"Existing scraping logic is duplicated across boards — v0.4 should not introduce a 6th copy of the same per-source pattern; build one ATS dispatcher with provider modules."* One file per provider, one Provider protocol in `base.py`, registry in `providers/__init__.py`. Adding Jobvite/Taleo in v0.5 = one new file + one entry in the registry — no churn elsewhere.

- **Why `references/ats-providers.md` AND `scripts/ats/providers/*.py` (duplication).** They serve different audiences: the markdown is for the LLM to read when reasoning ("the user pasted a `myworkday.jobs.com` URL — what is that?"), the Python is the ground truth used by the dispatcher. Same pattern as `scripts/schema.py` (truth) + `references/file-contract.md` (LLM's reading copy). The two must agree, but only the Python is invoked at runtime. To prevent drift: keep the markdown's "supported providers" table as a literal mirror of `PROVIDERS.keys()`, and add a one-line note that the Python is canonical.

- **Why a separate `/scout-detect` skill instead of a flag on `/scout-setup`.** Decision already locked in PROJECT.md ("New `/scout-detect` skill (vs. inline in scout-setup) — Reusable when companies are added later"). It's also a different cadence: `/scout-setup` runs once per machine, `/scout-detect` runs whenever the user adds 5+ companies to `master_targets.csv`. Different invocation, different skill.

- **Why `daily/<DATE>/ats_raw/` for raw provider responses.** Debuggability. When a company's count drops to 0 unexpectedly, having the raw JSON for that day means the user can see whether the provider returned 0, returned malformed data, or errored. ~5 files per run, ~50KB each — cheap. Created by `validate_data.py`.

- **Why `runs.jsonl` at `<data_dir>/runs.jsonl`, not under `daily/`.** It's append-only across runs (the whole point is trend tracking). Daily artifacts are scoped to one date. Putting it under `daily/<DATE>/` would either fragment the trend or require reading every daily folder. Top-level next to `master_targets.csv` matches its lifecycle.

---

## Architectural Patterns

### Pattern 1: Provider Protocol + Registry

**What:** Each ATS gets a single Python module exporting a fixed interface. A registry dict in `providers/__init__.py` maps provider name to module. Dispatcher and detector iterate the registry — they never name a specific provider.

**When to use:** Always — this is the load-bearing pattern that prevents per-source-pattern duplication.

**Trade-offs:**
- Pro: Adding Jobvite is one new file + one registry entry. No churn in dispatcher, normalizer, or skills.
- Pro: Each provider's quirks (Workday's POST body, Lever's `mode=json` query param, Ashby's auth header) are localized to that provider's `fetch()` function.
- Con: A bit more ceremony for the first provider. Pays back at provider #2.

**Example (`scripts/ats/providers/base.py`):**

```python
"""
base.py — Provider protocol and canonical Listing shape.

Every provider module must conform to the Provider protocol below.
The dispatcher and detector are written against this protocol — they
never import a specific provider directly.
"""

from dataclasses import dataclass, asdict
from typing import Protocol, Optional

@dataclass
class Listing:
    """Canonical ATS listing — one shape for all providers."""
    source: str                    # "ats"
    ats_provider: str              # "greenhouse" | "lever" | ...
    company: str                   # canonical company display name
    title: str                     # role title as posted
    location: str                  # primary location string
    apply_url: str                 # direct apply URL (NOT redirect)
    description: str               # full JD text (markdown or plain)
    posted_at: Optional[str]       # ISO date if available
    raw_id: str                    # provider's own ID — used for cross-run dedup

    def to_dict(self):
        return asdict(self)

class Provider(Protocol):
    NAME: str                       # e.g. "greenhouse"
    BOARD_URL_PATTERNS: list[str]   # regex patterns matching board URLs
    HOST_PATTERNS: list[str]        # regex patterns matching hosts that signal this provider

    def detect(self, url: str, html: Optional[str] = None) -> bool:
        """Return True if this URL/page belongs to this ATS."""

    def board_url_from_url(self, url: str) -> Optional[str]:
        """Given a career page or detected ATS URL, return the canonical
        board URL we'll later fetch from. None if can't normalize."""

    def fetch(self, board_url: str, timeout: int = 15) -> list[dict]:
        """Fetch raw provider JSON. Returns list of provider-shaped dicts.
        Raises requests.HTTPError on non-2xx. Returns [] on 200-with-no-jobs."""

    def to_listing(self, raw: dict, company: str) -> Listing:
        """Map one provider-shaped dict to a canonical Listing."""
```

```python
# scripts/ats/providers/__init__.py
from . import greenhouse, lever, ashby, smartrecruiters, workday

PROVIDERS = {
    p.NAME: p for p in (greenhouse, lever, ashby, smartrecruiters, workday)
}
```

### Pattern 2: Per-Provider Concurrency via Semaphore Map

**What:** A dict of `threading.Semaphore`, keyed by provider name. The dispatcher submits all (company × provider) calls to a single `ThreadPoolExecutor`, but each task acquires its provider's semaphore before making the HTTP call. Releases on completion or error.

**When to use:** When you have N providers, each with a different polite-concurrency tolerance, and you want one logical worker pool but isolated rate-limiting.

**Trade-offs:**
- Pro: One executor, one queue, one place to look when things go wrong.
- Pro: Per-provider caps mean Workday's slow tenants never starve Greenhouse fanout.
- Pro: Caps are tunable from `config.json` without touching code.
- Con: A blocked semaphore consumes a thread slot. Mitigation: pool size = sum of caps × 1.5 (safety margin).
- Con: Threading not asyncio — but threading is fine for I/O-bound HTTP, fits Python 3.8 minimum, and matches the "no new framework" constraint in PROJECT.md.

**Example (`scripts/ats/dispatcher.py`):**

```python
"""
dispatcher.py — Concurrent ATS fetch with per-provider concurrency caps.

CLI:
    python3 scripts/ats/dispatcher.py fetch-all <targets.json> <output.json>

Where targets.json is a list of {"company": ..., "provider": ..., "board_url": ...}.
Output is a list of canonical Listing dicts plus a stats block.
"""
import json, sys, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from .providers import PROVIDERS

DEFAULT_CAPS = {
    "greenhouse": 8, "lever": 8, "ashby": 8,
    "smartrecruiters": 6, "workday": 4,   # workday is slowest
}

def fetch_all(targets, caps=None, total_workers=None):
    caps = {**DEFAULT_CAPS, **(caps or {})}
    sems = {name: threading.Semaphore(n) for name, n in caps.items()}
    total_workers = total_workers or sum(caps.values()) + 4

    listings, errors, timings = [], [], {}

    def one(target):
        provider = PROVIDERS.get(target["provider"])
        if not provider:
            return ("skipped", target, "unknown provider")
        sem = sems[target["provider"]]
        t0 = time.monotonic()
        with sem:
            try:
                raw = provider.fetch(target["board_url"])
                return ("ok", [provider.to_listing(r, target["company"]) for r in raw], time.monotonic() - t0)
            except Exception as e:
                return ("err", target, f"{type(e).__name__}: {e}")

    with ThreadPoolExecutor(max_workers=total_workers) as ex:
        futures = [ex.submit(one, t) for t in targets]
        for f in as_completed(futures):
            kind, payload, extra = f.result()
            if kind == "ok":
                listings.extend(payload)
            elif kind == "err":
                errors.append({"company": payload["company"], "provider": payload["provider"], "error": extra})
            # "skipped" → also tracked in errors

    return {"listings": [l.to_dict() for l in listings],
            "errors": errors,
            "stats": {"providers": list(caps.keys()), "total_targets": len(targets)}}
```

### Pattern 3: Detection-as-CLI, Sharing Code Between Skills

**What:** Detection logic lives in `scripts/ats/detect.py` with two subcommands: `detect-one <company> <career_page_url>` (one company, prints JSON) and `detect-batch <input.csv> <output.csv>` (top-N from `master_targets.csv`, writes back). Both `/scout-detect` (uses `detect-batch`) and `/scout-run` (uses `detect-one` for the lazy inline path) call the same script — no duplication.

**When to use:** Always — anything that two skills both need is, by the existing convention, a script.

**Trade-offs:**
- Pro: Detection logic exists in exactly one place. If we later improve, e.g., the Workday host-sniffing heuristic, both skills inherit it.
- Pro: Subcommands match the existing `scripts/state.py {read|write|resolve}` and `scripts/tracker_utils.py {dedup-set|append|rebuild}` convention.
- Con: Two CLIs in one file means slightly bigger file. Acceptable — same as `tracker_utils.py` (346 lines).

**Example (subcommand shape, matches existing conventions):**

```python
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 -m scripts.ats.detect <command> [args...]")
        print("Commands: detect-one <company> <url>")
        print("          detect-batch <master_targets.csv> [--limit 30]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "detect-one":
        company, url = sys.argv[2], sys.argv[3]
        result = detect_one(company, url)
        print(json.dumps(result))
    elif cmd == "detect-batch":
        path = os.path.expanduser(sys.argv[2])
        limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 30
        results = detect_batch(path, limit=limit)
        print(json.dumps({"detected": len(results), "results": results}, indent=2))
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr); sys.exit(1)
```

### Pattern 4: Skill Holds Sequencing, Script Holds Determinism

**What:** This is the existing pattern — restated here because it's the load-bearing constraint for the whole milestone. The skill markdown lists the steps in order; each step's *deterministic* work is a CLI call. Anything requiring LLM judgement (deciding whether two slightly-different titles are the same role for dedupe, choosing the right resume version, writing the report narrative) stays in markdown.

**When to use:** Always. Don't write Python for things that need judgement. Don't write prompts for things that need to be identical every run.

**Boundary call-outs for v0.4:**

| Decision | In markdown (skill) | In Python (script) | Why |
|---|---|---|---|
| Provider detection | "if multiple providers match, pick the one whose board has more jobs" | URL/host regex matching, HTTP fetch, response sniffing | Regex match is deterministic; the rare ambiguity gets escalated to the LLM |
| Concurrent fetch | "call `dispatcher.py fetch-all`" | All of it | Threading + per-provider caps must be exact every time |
| Pass 1 → Pass 2 dedupe | Reading the dedupe report and noting any borderline cases in the narrative | `normalize_company_name`, `normalize_title`, fuzzy match, return Pass 2 minus matches | Dedupe rules can't drift |
| Tier bump | "for any Listing where `source = ats`, add 1 to its tier_score before threshold comparison" | Score arithmetic stays in the prompt; the rule is in markdown, the calculation is small enough to inline | Scoring already lives in the prompt — keep it there |
| Enrich-then-tier | Drive the LinkedIn shared-connection lookup for ATS A-candidates via Chrome MCP, attach connection names to the Listing, then re-evaluate tier | None — Chrome MCP is the side effect | Chrome interaction is judgement-driven (lazy-load timing, redirect handling) |
| Run summary | Compose the chat summary block | `runs_log.py append-run <stats.json>` writes the JSONL line | Stats schema must be stable for trend tracking |

### Pattern 5: Two-Stage Dedupe Boundary

**What:** Dedupe happens at exactly two points: (1) `dedupe.py` removes Pass 2 listings that overlap Pass 1 (cross-pass), (2) existing `tracker_utils.py dedup-set` removes anything already in `JobScout_Tracker.xlsx` (cross-run). They use different keys: cross-pass uses `(company_slug, normalized_title)` because LinkedIn URLs and ATS apply URLs are different; cross-run uses LinkedIn job ID. Don't conflate.

**When to use:** This is a constraint, not a choice — putting both dedupes in one place would force a single key, and LinkedIn job IDs aren't available for ATS listings.

**Trade-offs:**
- Pro: Each dedupe key matches its real-world identifier — no false merges.
- Con: Two passes. Acceptable — both are O(n) over a few hundred rows.

---

## Data Flow

### One full `/scout-run` (the canonical request flow)

```
[User: /scout-run]
    ↓
[Step 0: state.py resolve, validate_data.py]
    ↓                                     (creates daily/<DATE>/ats_raw/, ensures runs.jsonl exists)
[Step 1: load config, profile, master_targets.csv, dedup-set]
    ↓
[Step 2: PASS 1 — ATS]
    │
    ├─ 2a. Filter master_targets.csv: rows with ats_provider != "" and != "unknown"
    │      Sort by linkedin_connection_count desc, last_checked asc.
    │      Take top N (where N = pass1_company_budget from config).
    │
    ├─ 2b. For any row in that top-N where ats_provider == "" → LAZY DETECT:
    │      python3 -m scripts.ats.detect detect-one <company> <career_page_url>
    │      Capture result, write back to master_targets.csv (in-memory now,
    │      flushed at Step 8). If detect returns "unknown", drop the row from
    │      Pass 1 — it'll fall through to Pass 2 by name in Step 3.
    │
    ├─ 2c. Build targets.json = [{company, provider, board_url}, ...]
    │      Write to <data_dir>/daily/<DATE>/ats_raw/targets.json (debuggable).
    │
    ├─ 2d. python3 -m scripts.ats.dispatcher fetch-all
    │           <data_dir>/daily/<DATE>/ats_raw/targets.json
    │           <data_dir>/daily/<DATE>/ats_raw/listings.json
    │      → produces canonical Listing[] + per-provider stats + errors[].
    │      → tag each listing source="ats", ats_provider=<name>.
    │
    ├─ 2e. Optionally: write per-provider raw JSON to ats_raw/<provider>.json
    │      (dispatcher already has it — emit on a flag for debuggability).
    │
    └─ 2f. PASS 1 RESULT: pass1_listings = listings.json contents.
           Drop anything whose raw_id is in dedup-set (already tracked).
    ↓
[Step 3: PASS 2 — LinkedIn keyword]
    │
    ├─ 3a. Run config.search.queries (and underutilized_asset_queries) against LinkedIn
    │      via Chrome MCP. Same as today.
    │
    ├─ 3b. For each LinkedIn result, build a Listing dict (source="linkedin",
    │      ats_provider=None). Capture LinkedIn job ID.
    │
    ├─ 3c. python3 -m scripts.ats.dedupe dedupe-pass2
    │           <pass1_listings.json> <pass2_raw.json> <pass2_clean.json>
    │      → writes Pass 2 minus anything fuzzy-matching Pass 1 by
    │        (normalize_company_name, normalize_title).
    │
    └─ 3d. Drop anything in pass2_clean whose LinkedIn job ID is in dedup-set.
    ↓
[Step 4: SCORE all listings, apply +1 ATS bump]
    │
    ├─ 4a. For each listing in (pass1_listings + pass2_clean), apply scoring
    │      rubric (in-prompt, per scoring-rubric.md).
    │
    └─ 4b. If listing.source == "ats", tier_score += 1 BEFORE threshold check.
           (This is a prompt rule, not a script — see Pattern 4 boundary table.)
    ↓
[Step 5: ENRICH-THEN-TIER for ATS A-candidates]
    │
    ├─ 5a. Take all listings where source == "ats" AND provisional tier == "A".
    │
    ├─ 5b. For each, look up shared-connection enrichment via LinkedIn (Chrome MCP):
    │      navigate to company page, capture "you and X share Y connections" block.
    │      This is the only Chrome work for ATS listings.
    │
    ├─ 5c. Attach connection_names to the Listing, re-run scoring (Connection
    │      Leverage category will now have data). Re-assign tier.
    │
    └─ 5d. If new tier != A, demote (or promote — but rare). Cap at 10 A-tier total.
    ↓
[Step 6: WRITE report]
    │
    ├─ 6a. Compose JobScout_Report_<DATE>.md per existing format, plus:
    │      - Source tag per listing: "ATS (greenhouse)" or "LinkedIn keyword"
    │      - Pass 1 share %: "Pass 1 contributed 7/12 A-tier (58%)"
    │      - Wall-clock summary
    │
    ├─ 6b. Write new_rows.json (per existing TRACKER_JSON_KEYS).
    │
    └─ 6c. Write run_log.json with per-pass counts, per-provider stats from dispatcher.
    ↓
[Step 7: APPEND tracker]
    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tracker_utils.py append <tracker> <new_rows.json>
    (unchanged from today)
    ↓
[Step 8: PERSIST master_targets updates]
    │
    ├─ 8a. Update last_checked for all visited companies.
    │
    ├─ 8b. Write back any ats_provider/ats_board_url discovered during Step 2b
    │      lazy detect.
    │
    └─ 8c. Append new "scout_discovered" companies surfaced in Pass 2.
    ↓
[Step 9: APPEND runs.jsonl]
    python3 -m scripts.ats.runs_log append-run <stats.json>
    Records: {date, wall_clock_s, pass1_count, pass2_count, ab_total,
              pass1_ab_share, per_provider: {greenhouse: {ok, err, listings}, ...}}
    ↓
[Step 10: CHAT SUMMARY] (existing)
```

### State Management

```
master_targets.csv (incremental, partial-rewrites)
    ↓ (read at Step 1, partial update at Step 8)
    ats_provider/ats_board_url columns: filled by /scout-detect (batch),
    backfilled lazily by /scout-run Step 2b.

runs.jsonl (append-only, never rewritten)
    ↓ (one new line per /scout-run, written at Step 9)
    Source of truth for the "Pass 1 ≥60% of A/B-tier" milestone bar.

JobScout_Tracker.xlsx (append-only, written ONLY by tracker_utils.py)
    Unchanged — same dedup-by-LinkedIn-job-ID. ATS rows go in with their
    apply URL in the Job URL column; "Connections" column carries enriched
    names from Step 5.
```

### Key Data Flows

1. **Detection flow (`/scout-detect`):** Read `master_targets.csv` → take top-30 by `linkedin_connection_count` → for each, call `detect.py detect-one` → batch-write `ats_provider` + `ats_board_url` back. One CSV pass, no scoring, no Chrome.

2. **Daily run flow (`/scout-run`):** As diagrammed above. Two passes (ATS first, LinkedIn second), one cross-pass dedupe, one enrich step for A-candidates, one tracker append, one runs.jsonl append.

3. **Lazy-detect side flow:** Inside Step 2b of `/scout-run`, any company in the day's Pass 1 sample without an `ats_provider` triggers `detect-one`. Result is held in memory, persisted at Step 8. Cached forever (until detection logic is upgraded — bump a version somewhere if we want to invalidate).

4. **Debug flow:** Raw provider JSON lands at `daily/<DATE>/ats_raw/<provider>.json` per run. If a company had jobs yesterday and zero today, the user can `cat ats_raw/greenhouse.json | jq '.[] | select(.company == "Acme")'` and see whether it's a real change or a fetch error.

---

## Build-Order Implications

This is the recommended phase ordering for the v0.4 milestone, with rationale:

| Order | Phase | Why this slot |
|---|---|---|
| **1. Schema + paths first** | Add `runs.jsonl` and `daily/<DATE>/ats_raw/` to `validate_data.py` and `file-contract.md`. (Schema columns `ats_provider`/`ats_board_url` are *already* in `scripts/schema.py` — verify and don't re-add.) Bump `MASTER_TARGETS_VERSION` only if anything changes. | Smallest diff. Unblocks every later phase to write artifacts to known paths. Zero behavior change for users still on v0.3. |
| **2. Provider Protocol + ONE end-to-end provider (Greenhouse)** | Build `scripts/ats/providers/base.py`, `providers/greenhouse.py`, `dispatcher.py`, `normalize.py`. Wire a stub `/scout-run` invocation that does Greenhouse-only Pass 1 and merges into the existing flow without touching Pass 2. | Validates the *whole* dispatcher + normalize + Listing-shape decision against real data before paying the cost of 4 more providers. If the Listing dataclass is wrong, you find out at provider #1, not provider #5. Greenhouse first because its API is the simplest (`api.greenhouse.io/v1/boards/{name}/jobs?content=true`, public, no auth, well-documented). |
| **3. Detection (`scripts/ats/detect.py` + `/scout-detect` skill)** | Add detection for Greenhouse only at this point. Then add the `/scout-detect` skill that batch-detects top-30 and writes back to `master_targets.csv`. Add lazy detect in `/scout-run` Step 2b. | Once one provider's fetch path is proven, detection can be added against it without risking the fetch path. Lazy detect is essentially the same call from a different caller — minimal new code. |
| **4. Remaining providers (Lever, Ashby, SmartRecruiters, Workday)** | One provider per chunk. Each is a new file in `providers/` + a registry entry + a `BOARD_URL_PATTERNS` addition + a row in the `references/ats-providers.md` matrix. Workday last because its tenant URLs and POST body are messier. | Provider Protocol absorbs all variation. By this point dispatcher, normalizer, detector, and `/scout-detect` are all stable — provider work is purely additive. |
| **5. Pass 2 dedupe + ATS tier bump + enrich-then-tier** | `dedupe.py` with the fuzzy-match. Markdown change in `scoring-rubric.md` for the +1 bump. New step in `scout-run/SKILL.md` for enrich-then-tier with Chrome MCP. | These all depend on multi-provider results actually existing, so they come after Phase 4. Dedupe and enrich can be parallel sub-tasks. |
| **6. Run-log + summary block + delete legacy code** | `scripts/ats/runs_log.py append-run`. Final chat-summary block in `scout-run/SKILL.md`. Delete the marketing-page Chrome scraping code from `scout-run/SKILL.md` and trim `chrome-setup.md`. | The deletion is best done last — once we know Pass 1 is producing the ≥60% A/B share, ripping out the old code is safe and the milestone definition explicitly requires it. |

**Why "Greenhouse first end-to-end" matters more than "all five providers in parallel":** the highest-risk decisions in this milestone are the canonical Listing shape, the dispatcher's per-provider concurrency model, and the protocol contract. If any of those need revision, doing it after one provider is ~1 day of refactor; after five providers it's ~3 days. Build-order minimizes the cost of being wrong.

**Skill prompts can stay on v0.3 fully working until Phase 5.** Phases 2–4 only add a new code path. The existing 3-pass flow keeps running unchanged. Phase 5/6 is when `scout-run/SKILL.md` becomes a 2-pass + enrich rewrite.

---

## Scaling Considerations

This is a single-user CLI plugin — "scaling" here means: how does the architecture hold up as the master_targets list grows, as more providers are added, and as runs accumulate?

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 30–100 companies in master_targets | No changes. Dispatcher handles 100× concurrent calls in seconds. |
| 100–500 companies | Add `--max-companies-per-pass` to dispatcher CLI; let Pass 1 sample top-N rather than fetch all. The "top-N by connection_count + last_checked staleness" already exists in master_targets sorting — extend it to ATS Pass 1 explicitly. |
| 500+ companies, or adding 5+ providers | Consider provider-shard caching: cache `(provider, board_url) → listings` for ≤6 hours so repeat runs in a day don't refetch. Local-disk JSON cache, gated by ATS-Last-Modified header where the provider supports it (Greenhouse does; Workday doesn't). |
| 365+ runs.jsonl entries | Add `runs_log.py compact` command that summarizes month-old entries to weekly aggregates. Not urgent — JSONL with one line per day is ~110KB/year. |

### Scaling Priorities

1. **First bottleneck: Workday wall-clock.** Workday tenants are slow (1–3 sec per fetch typical). With 30 Workday companies and concurrency cap 4, that's 30/4 × 2 sec = ~15 sec just for Workday. This will dominate the 5-minute budget if the user has many Workday targets. Mitigation: bump Workday cap or cache responses for the day.

2. **Second bottleneck: LinkedIn enrichment for ATS A-candidates.** Chrome MCP navigation is sequential and ~3–5 sec per company. With 10 A-candidates that's 30–50 sec. Acceptable in v0.4. If it grows, batch into a single Chrome session and parallelize via tabs.

3. **Third bottleneck: master_targets.csv full-rewrite at Step 8.** Currently a full pandas read/write. At >5000 rows this will be slow. Mitigation deferred — the user's list is unlikely to exceed 500.

---

## Anti-Patterns

### Anti-Pattern 1: Per-Provider Branching in the Skill Prompt

**What people do:** Add a `## Step 2 (Greenhouse)`, `## Step 3 (Lever)`, etc. to `scout-run/SKILL.md`, with provider-specific URL templates and parsing instructions inline.

**Why it's wrong:** Re-introduces exactly the duplication the codebase concerns called out as the v0.4 anti-goal. The prompt would balloon, would drift from the Python registry, and adding Jobvite would mean editing both the prompt and the code.

**Do this instead:** The prompt has one Pass 1 step that calls `dispatcher.py fetch-all` and gets back a uniform Listing list. The prompt never names a specific ATS provider in instructional text — only in narrative report-writing where it's a label.

### Anti-Pattern 2: Sleep-Between-Requests "Politeness"

**What people do:** Add `time.sleep(0.5)` between provider calls "to be polite" — common in legacy scrapers.

**Why it's wrong:** PROJECT.md explicitly rejects this ("ATS APIs are called concurrently with a per-provider concurrency cap (no fixed sleep between requests)"). Sleep gives the *illusion* of politeness but doesn't actually bound concurrent load — two parallel runs each sleeping is still 2× concurrency at the provider. Concurrency caps are the real solution.

**Do this instead:** Per-provider semaphore (Pattern 2). The cap *is* the politeness contract. If a provider rejects, lower the cap in `config.json` for that provider only.

### Anti-Pattern 3: Falling Back to Chrome on ATS Error

**What people do:** "If the Greenhouse API returns 0 jobs, try scraping the Greenhouse board page in Chrome as a backup."

**Why it's wrong:** PROJECT.md ("Trust ATS on 0/error (no Chrome fallback)"). The whole milestone is about removing the fragile Chrome path. A fallback re-introduces the fragility while pretending we removed it. If the ATS returns 0, the company has no openings — accept it and move on.

**Do this instead:** Log the 0/error in `run_log.json` and `ats_raw/` for debuggability. Move on. If a specific provider's API is so flaky that real openings get missed, address it in v0.5 with a provider-specific strategy — not a generic Chrome fallback.

### Anti-Pattern 4: Inlining the Listing Shape in the Prompt

**What people do:** Have `scout-run/SKILL.md` describe what fields a Listing has, what JSON keys to expect from `dispatcher.py`, etc.

**Why it's wrong:** Same drift problem as inlining schemas — covered by the "Schemas in `scripts/schema.py`, paths in `file-contract.md`" convention. The Listing dataclass *is* the shape; the prompt should refer to it by name.

**Do this instead:** The Listing dataclass lives in `scripts/ats/providers/base.py`. `references/ats-providers.md` has a "Listing shape" table that mirrors the dataclass field names. Prompt reads the reference doc, doesn't inline.

### Anti-Pattern 5: One Giant `scripts/ats.py` File

**What people do:** Put all the ATS code in one `scripts/ats.py` because "it's not that much code yet."

**Why it's wrong:** It will be ~2000 lines by Phase 4 (5 providers × 200 lines + dispatcher + detect + normalize + dedupe). One-file-per-provider is the explicit win the package layout buys us — splits review effort, isolates provider-specific test surface, scopes future Jobvite work.

**Do this instead:** Package layout from the start. The first commit can stub all 5 provider files with just `NAME = "..."` and `BOARD_URL_PATTERNS = []`; fill them in as Phase 4 progresses.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Greenhouse Job Board API | `GET https://boards-api.greenhouse.io/v1/boards/{name}/jobs?content=true` — no auth | Cleanest of the five. Returns full JD HTML in `content` field. |
| Lever Postings API | `GET https://api.lever.co/v0/postings/{name}?mode=json` — no auth | Returns array of postings. JD in `descriptionPlain`. Dead simple. |
| Ashby Job Board API | `GET https://api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true` — no auth | Some boards require `includeJobs=true` query — sniff response shape. |
| SmartRecruiters Postings | `GET https://api.smartrecruiters.com/v1/companies/{name}/postings` — no auth for public boards | Pagination via `offset`/`limit`. Cap at 1 page (100 listings) for v0.4. |
| Workday CXS | `POST https://{tenant}.wd1.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` — no auth, but needs tenant + site discovery | Most fragile of the five. PROJECT.md OOS: "if a tenant requires session/CSRF tokens beyond the public POST endpoint, that company falls through to Pass 2." Honor that. |
| Chrome MCP (`mcp__Claude_in_Chrome__*`) | Existing skill tool | v0.4 use is restricted to (a) Pass 2 LinkedIn keyword search, (b) Step 5 LinkedIn enrichment for ATS A-candidates. NOT used for career page scraping (deleted). |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Skill (`scout-run`, `scout-detect`) ↔ scripts | `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/...` shell call, JSON over stdout | Existing pattern. Always JSON for machine-consumed output, last `print()` of the CLI. |
| `scripts/ats/dispatcher.py` ↔ `scripts/ats/providers/<name>.py` | Direct Python import of the providers registry | One process; dispatcher is the only caller of `provider.fetch()`. |
| `scripts/ats/detect.py` ↔ providers | Direct Python import; iterates `PROVIDERS.items()` | Detector and dispatcher both use the registry — never name a provider directly. |
| Skill prompts ↔ schema | Reference by name (`MASTER_TARGETS_COLUMNS`, `Listing`) | Never inline column lists. Same convention as today. |
| `scripts/ats/*` ↔ `scripts/schema.py` | Sibling import via the existing `SCRIPTS_DIR` bootstrap, OR `from ..schema import ...` if invoked as a package module | Consistent with `validate_data.py`, `tracker_utils.py`, `consolidate_targets.py` — they all bootstrap then `from schema import ...`. |
| `scripts/ats/runs_log.py` ↔ `<data_dir>/runs.jsonl` | Append-only file write, one line per run | Single writer. Schema for the JSONL line documented in the script's module docstring. |

---

## Schema Note

`scripts/schema.py` **already includes** `ats_provider` and `ats_board_url` in `MASTER_TARGETS_COLUMNS` (verified at `scripts/schema.py:26-27`), and `MASTER_TARGETS_VERSION = 3` already reflects this. The PROJECT.md requirement to "extend MASTER_TARGETS_COLUMNS" is satisfied at the schema layer; what's missing is the Python code that populates these columns and the skills that invoke that code. Phase 1 (schema + paths) is therefore mostly *path/JSONL* work, not column work — verify and move on.

If the team chooses to also tag the tracker rows with source/provider (so the user can filter ATS-vs-LinkedIn rows in Excel), `TRACKER_COLUMNS` and `TRACKER_JSON_KEYS` would need additions and `MASTER_TARGETS_VERSION` is unaffected — but this is a separate decision not currently called out in PROJECT.md and should be raised explicitly in Phase 1 planning, not slipped in.

---

## Sources

- [How to Build a Job Board Integrating Greenhouse, Lever, and 73+ ATS Platforms](https://unified.to/blog/how_to_build_a_job_board_integrating_greenhouse_lever_and_73_ats_platforms_with_an_ats_api) — confirms public API endpoint shapes for Greenhouse, Lever, Ashby (HIGH for endpoints; MEDIUM for current behavior — verify per-provider as Phase 4 hits each)
- [15 ATS APIs to Integrate With in 2026](https://unified.to/blog/15_ats_apis_to_integrate_with_in_2026_greenhouse_lever_workable) — current as of 2026, confirms Greenhouse/Lever/Ashby are the easy three (HIGH)
- [jobber: Super simple API to fetch job listings from popular job boards](https://github.com/plibither8/jobber) — reference implementation showing the exact shape Pattern 1 (Provider registry) takes in practice (HIGH)
- [6 ATS Platforms with Public Job Posting APIs](https://fantastic.jobs/article/ats-with-api) — corroborates the public-API status of the five chosen providers (MEDIUM)
- [Limit concurrency with semaphore in Python asyncio](https://rednafi.com/python/limit-concurrency-with-semaphore/) — pattern reference for per-host concurrency; threading equivalent is straightforward (HIGH for the pattern, threading translation is mechanical)
- [Python concurrent.futures docs (3.14)](https://docs.python.org/3/library/concurrent.futures.html) — official reference for ThreadPoolExecutor (HIGH)
- Codebase analysis: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`, `.planning/codebase/CONVENTIONS.md` — existing patterns this milestone must respect (HIGH)
- `.planning/PROJECT.md` — locked-in decisions for v0.4 (HIGH)
- `scripts/schema.py` (verified line 26-27 already contains `ats_provider` and `ats_board_url`) — material correction to PROJECT.md's claim that schema "extends" these columns (HIGH)

---

*Architecture research for: ATS-first sourcing layer in job-scout v0.4*
*Researched: 2026-04-27*

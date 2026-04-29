"""
dispatcher.py — Concurrent ATS fetch with per-provider semaphores + 3-state outcomes.

Locked Phase 2 decisions implemented here:
  DSP-03: ONE shared httpx.Client (instantiated once per run, closed in
          `finally`), with httpx.Timeout(connect=5, read=15) on every call.
  DSP-04: ThreadPoolExecutor(max_workers=20) + per-provider
          threading.Semaphore. Caps loaded from config.json
          (ats.provider_concurrency_caps); defaults match research/STACK.md.
  DSP-05: Three-state outcome per (company, provider): OK_WITH_RESULTS
          (n>=1 listings), OK_ZERO (200 + 0 jobs), ERROR (any non-200,
          network failure, parse failure). All three logged to runs.jsonl.
  DSP-06: Worker exception wrapper captures + logs + bucket-as-ERROR; the
          caller (skill code) sees aggregated outcomes instead of raw raises.
  DSP-08: ats.concurrency_disabled kill-switch — when true, falls back to
          sequential per-provider fetches (no executor, no semaphores).
          Same code path otherwise.

Anti-features baked-in (locked):
  - NO retry-on-403/429 within a run. "Tomorrow's run" is the correct
    backoff. (PROJECT.md anti-feature.)
  - NO Chrome fallback on 0/error. (PROJECT.md milestone-defining decision.)
  - NO worker-thread tracker writes. The dispatcher returns aggregated
    outcomes; the skill (or future ats/dedupe.py) calls tracker_utils.append
    on the main thread. (PITFALLS Pitfall 5: shared-state bugs.)
"""

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

try:
    import httpx
except ImportError:
    print(
        "ERROR: httpx not installed. Install with: "
        "python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate && pip install 'httpx>=0.27,<0.29'"
        "  (or: pip install --user 'httpx>=0.27,<0.29')."
        "  Note: pipx is for standalone CLI tools; httpx is a library and belongs in a project venv or user-site install.",
        file=sys.stderr,
    )
    sys.exit(1)

# Sibling-script bootstrap (2-level — file → ats → scripts).
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
from ats import PROVIDERS  # noqa: E402
from ats.normalize import Listing  # noqa: E402
from ats.providers.base import DetectionResult, FetchResult  # noqa: E402,F401
from ats.runs_log import RunOutcome, append_run  # noqa: E402,F401


# Per-provider concurrency caps. From research/STACK.md (HIGH confidence,
# derived from observed latency + tenant-isolation patterns). Caps live in
# config.json under ats.provider_concurrency_caps; this dict is the FALLBACK
# if config.json doesn't override (matches "single source of truth" but
# tolerates a missing key).
DEFAULT_PROVIDER_CAPS = {
    "greenhouse": 10,
    "ashby": 8,
    "lever": 5,
    "smartrecruiters": 5,
    "workday": 3,
}

# Total executor pool size. Matches sum of caps (31) + headroom; capped at
# 20 because Phase 2 only exercises greenhouse (cap=10) and 20 still
# honors the per-provider caps when Phase 4 ships the rest.
DEFAULT_MAX_WORKERS = 20

# httpx defaults — explicit timeout on every request (DSP-03).
# httpx >= 0.28 requires either a `default` or all four (connect, read,
# write, pool) explicitly. We keep connect=5 / read=15 from the locked
# decision and pin write/pool to read=15 so a slow tenant can't hang on
# upload or connection-pool acquisition either.
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=15.0, pool=15.0)

# User-Agent — some Workday tenants 403 on default Python UAs (per
# research/STACK.md). Phase 4 hits this; setting it now is free.
DEFAULT_USER_AGENT = "job-scout/0.4 (+claude-code-plugin)"

# Module-level mutable: per-provider semaphores. Lazy-initialized on first
# fetch_all() call so config.json overrides can take effect (the caller
# passes the loaded caps).
_SEMAPHORES: Dict[str, threading.Semaphore] = {}
_SEMAPHORE_LOCK = threading.Lock()


@dataclass
class FetchOutcome:
    """Per-(company, provider) outcome from one fetch attempt."""

    company_slug: str
    provider: str
    outcome: RunOutcome  # OK_WITH_RESULTS | OK_ZERO | ERROR
    listings: List[Listing] = field(default_factory=list)
    raw: List[Dict[str, Any]] = field(default_factory=list)
    http_status: int = -1
    error: Optional[str] = None  # populated on ERROR; (type, message) string
    elapsed_seconds: float = 0.0


def load_caps_and_kill_switch(config_path: str) -> Tuple[Dict[str, int], bool]:
    """Read config.json's ats.provider_concurrency_caps and ats.concurrency_disabled.

    Falls back to DEFAULT_PROVIDER_CAPS if the section is missing. The
    kill-switch defaults to False. Reads happen ONCE per /scout-run at
    the entry to fetch_all() — config changes mid-run are ignored.

    Threat T-02-08 mitigation: malformed config.json (JSONDecodeError, OSError)
    triggers a stderr WARNING and falls back to defaults. Cap values must be
    positive ints — invalid types are silently dropped (the warning above
    surfaces the file-level problem; per-key garbage is ignored). The
    kill-switch is coerced via bool() so non-true values flow to False.
    """
    caps = dict(DEFAULT_PROVIDER_CAPS)
    kill = False
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            ats = cfg.get("ats", {})
            user_caps = ats.get("provider_concurrency_caps", {})
            for k, v in user_caps.items():
                if isinstance(v, int) and v > 0:
                    caps[k] = v
            kill = bool(ats.get("concurrency_disabled", False))
        except (OSError, json.JSONDecodeError) as e:
            print(
                f"WARNING: could not parse {config_path} (using defaults): {e}",
                file=sys.stderr,
            )
    return caps, kill


def _init_semaphores(caps: Dict[str, int]) -> None:
    """Initialize the module-level _SEMAPHORES dict from a caps dict.

    Single global per-provider semaphore (NOT per-thread) — see PITFALLS
    Pitfall 5. Held under _SEMAPHORE_LOCK so concurrent fetch_all() calls
    in the same process don't race the dict swap.

    Mutates _SEMAPHORES in place (clear + update) rather than rebinding
    the global, so callers that imported _SEMAPHORES via
    `from ats.dispatcher import _SEMAPHORES` see the new contents. (Plain
    rebinding would leave external imports pointing at the old dict.)
    """
    with _SEMAPHORE_LOCK:
        _SEMAPHORES.clear()
        _SEMAPHORES.update({p: threading.Semaphore(n) for p, n in caps.items()})


@contextmanager
def _gate(provider: str) -> Iterator[None]:
    """Context manager that acquires the per-provider semaphore for the duration.

    Falls back to a Semaphore(1) if the provider isn't in _SEMAPHORES (config
    drift); logs a stderr WARNING so the operator notices. Fail-safe: an
    unknown provider gets serialized rather than unbounded.
    """
    sem = _SEMAPHORES.get(provider)
    if sem is None:
        print(
            f"WARNING: no semaphore configured for provider {provider!r}; using Semaphore(1)",
            file=sys.stderr,
        )
        sem = threading.Semaphore(1)
    sem.acquire()
    try:
        yield
    finally:
        sem.release()


def _execute_one(
    company_slug: str,
    provider_name: str,
    client: "httpx.Client",
) -> FetchOutcome:
    """Run one (company, provider) fetch. Catches all exceptions, buckets as ERROR.

    DSP-06 (two-tier handling per the updated REQUIREMENTS.md DSP-06 wording):

    Tier 1 — RE-RAISE: KeyboardInterrupt, MemoryError, SystemExit. These
    are unrecoverable signals (user Ctrl-C, OOM, sys.exit() inside a
    provider). Bucketing them as ERROR would silently swallow operator
    intent and OS conditions; instead we propagate them out of the worker
    thread, where ThreadPoolExecutor surfaces them via Future.result()
    in fetch_all and the run halts.

    Tier 2 — BUCKET AS ERROR: every other Exception subclass. These are
    recoverable per-fetch failures — httpx.HTTPError (transport),
    httpx.HTTPStatusError (4xx/5xx), JSONDecodeError, ValueError from
    Listing.__post_init__ (missing required field per DSP-02), provider
    parse errors. Each gets logged to stderr with (provider, company,
    error_type, error_message) context AND returned as a FetchOutcome with
    outcome=ERROR so it's visible in runs.jsonl. The Future returned by
    ThreadPoolExecutor.submit() is then always-successful from the
    executor's POV (no swallowed Future.exception()) — the caller iterates
    outcomes and sees ERROR explicitly with the message.
    """
    provider = PROVIDERS.get(provider_name)
    if provider is None:
        return FetchOutcome(
            company_slug=company_slug,
            provider=provider_name,
            outcome=RunOutcome.ERROR,
            error=f"unknown provider {provider_name!r} (not in PROVIDERS registry)",
        )
    sem = _SEMAPHORES.get(provider_name)
    if sem is None:
        return FetchOutcome(
            company_slug=company_slug,
            provider=provider_name,
            outcome=RunOutcome.ERROR,
            error=f"no semaphore for provider {provider_name!r} (config drift)",
        )

    t0 = time.monotonic()
    try:
        with _gate(provider_name):
            fetch_result = provider.fetch(company_slug, client, sem)
        elapsed = time.monotonic() - t0
        # PRV-05 / D-1: surface auth_required as a distinguishable OK_ZERO with
        # error="<provider>_auth_required". The non-None error field is what makes
        # it visible in runs.jsonl per-(company, provider) entries
        # (aggregate_outcomes + append_run already plumb FetchOutcome.error to
        # the persistence path). Phase 5 will use this signal to route the
        # company to Pass 2 only — not silently swallow as OK_ZERO.
        # outcome=OK_ZERO + error=None  → regular zero (trust-on-zero)
        # outcome=OK_ZERO + error="workday_auth_required" → auth gate (route to Pass 2)
        if getattr(fetch_result, "auth_required", False):
            return FetchOutcome(
                company_slug=company_slug,
                provider=provider_name,
                outcome=RunOutcome.OK_ZERO,
                listings=[],
                raw=fetch_result.raw,
                http_status=fetch_result.http_status,
                error=f"{provider_name}_auth_required",
                elapsed_seconds=elapsed,
            )
        if not fetch_result.listings:
            return FetchOutcome(
                company_slug=company_slug,
                provider=provider_name,
                outcome=RunOutcome.OK_ZERO,
                listings=[],
                raw=fetch_result.raw,
                http_status=fetch_result.http_status,
                elapsed_seconds=elapsed,
            )
        return FetchOutcome(
            company_slug=company_slug,
            provider=provider_name,
            outcome=RunOutcome.OK_WITH_RESULTS,
            listings=fetch_result.listings,
            raw=fetch_result.raw,
            http_status=fetch_result.http_status,
            elapsed_seconds=elapsed,
        )
    except (KeyboardInterrupt, MemoryError, SystemExit):
        # DSP-06 (locked) two-tier exception handling: truly unrecoverable
        # exceptions re-raise and halt the run. Bucketing these as ERROR
        # would silently lose Ctrl-C and OOM signals — the user expects
        # those to propagate.
        raise
    except Exception as exc:  # noqa: BLE001 — DSP-06 recoverable catch-all
        # All recoverable per-fetch exceptions (httpx.HTTPError subclasses,
        # ValueError from to_listing's missing-required-field, JSONDecodeError,
        # etc.) bucket as ERROR with full (provider, company, error_type,
        # error_message) context. The dispatcher caller sees them via
        # runs.jsonl + stderr per the updated DSP-06 wording in REQUIREMENTS.md.
        elapsed = time.monotonic() - t0
        err = f"{type(exc).__name__}: {exc}"
        print(f"ERROR: {provider_name}/{company_slug}: {err}", file=sys.stderr)
        return FetchOutcome(
            company_slug=company_slug,
            provider=provider_name,
            outcome=RunOutcome.ERROR,
            error=err,
            elapsed_seconds=elapsed,
        )


def fetch_all(
    targets: List[Tuple[str, str]],
    config_path: str,
    client: Optional["httpx.Client"] = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> List[FetchOutcome]:
    """Concurrently fetch ATS listings for a list of (company_slug, provider_name) pairs.

    DSP-03: ONE shared httpx.Client. If the caller does not supply one, we
            instantiate it here and close it in `finally`. The Client is
            thread-safe (research/STACK.md HIGH confidence).
    DSP-04: ThreadPoolExecutor(max_workers=N) + per-provider semaphores
            from config.json. Semaphores are module-level so that
            near-simultaneous fetch_all() calls in the same process share
            the cap (matters for /scout-detect + /scout-run sharing this
            module in Phase 3+).
    DSP-08: When ats.concurrency_disabled is true in config.json, falls
            back to sequential per-task execution (no executor, no
            semaphores acquired beyond a Semaphore(1)). Same FetchOutcome
            shape returned. Same code path otherwise.

    The caller persists outcomes via runs_log.append_run (Plan 02-03 wires
    this into /scout-run; this module returns outcomes only).
    """
    caps, kill_switch = load_caps_and_kill_switch(config_path)
    if kill_switch:
        # Sequential fallback. Each provider gets a Semaphore(1) to keep
        # _gate() honest; the executor is replaced by a plain loop.
        _init_semaphores({p: 1 for p in caps})
        owned_client = client is None
        client = client or httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            follow_redirects=True,
        )
        try:
            return [_execute_one(slug, provider, client) for slug, provider in targets]
        finally:
            if owned_client:
                client.close()

    _init_semaphores(caps)
    owned_client = client is None
    client = client or httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": DEFAULT_USER_AGENT},
        limits=httpx.Limits(
            max_connections=max_workers, max_keepalive_connections=max_workers
        ),
        follow_redirects=True,
    )
    try:
        outcomes: List[FetchOutcome] = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                pool.submit(_execute_one, slug, provider, client)
                for slug, provider in targets
            ]
            for fut in futures:
                # _execute_one already catches all exceptions and returns
                # FetchOutcome — Future.result() should never raise here.
                # The .result() call IS DSP-06's defense against swallowed
                # exceptions: if _execute_one ever does raise (it shouldn't),
                # we surface it loudly.
                outcomes.append(fut.result())
        return outcomes
    finally:
        if owned_client:
            client.close()


def aggregate_outcomes(
    outcomes: List[FetchOutcome],
) -> Tuple[
    Dict[str, Dict[str, int]],
    Dict[str, Dict[str, Any]],
    Dict[str, List[Dict[str, Any]]],
]:
    """Aggregate a list of FetchOutcome into the three dicts append_run() expects.

    Returns:
        per_provider_outcomes: {"greenhouse": {"ok_with_results": N, "ok_zero": N, "error": N}}
        per_company_provider:  {"stripe|greenhouse": {"outcome": "OK_WITH_RESULTS", "listing_count": N}}
        per_provider_listings: {"greenhouse": [listing_dict, ...]}  (for field_completion)
    """
    per_provider: Dict[str, Dict[str, int]] = {}
    per_cp: Dict[str, Dict[str, Any]] = {}
    per_pl: Dict[str, List[Dict[str, Any]]] = {}
    for o in outcomes:
        counts = per_provider.setdefault(
            o.provider, {"ok_with_results": 0, "ok_zero": 0, "error": 0}
        )
        if o.outcome == RunOutcome.OK_WITH_RESULTS:
            counts["ok_with_results"] += 1
        elif o.outcome == RunOutcome.OK_ZERO:
            counts["ok_zero"] += 1
        else:
            counts["error"] += 1
        cp_record: Dict[str, Any] = {
            "outcome": o.outcome.value,
            "listing_count": len(o.listings),
            "http_status": o.http_status,
            "elapsed_seconds": round(o.elapsed_seconds, 3),
        }
        if o.error:
            cp_record["error"] = o.error
        per_cp[f"{o.company_slug}|{o.provider}"] = cp_record
        if o.listings:
            per_pl.setdefault(o.provider, []).extend(L.to_dict() for L in o.listings)
    return per_provider, per_cp, per_pl


if __name__ == "__main__":
    # Smoke test entry point — useful for Plan 02-02 + Plan 02-03 integration.
    # Skill code does not call this CLI; it imports fetch_all directly.
    if len(sys.argv) < 4:
        print(
            "Usage: python3 scripts/ats/dispatcher.py fetch-all <config.json> <targets.json>",
            file=sys.stderr,
        )
        print(
            '  targets.json: [{"company_slug": "stripe", "provider": "greenhouse"}, ...]',
            file=sys.stderr,
        )
        sys.exit(1)
    if sys.argv[1] != "fetch-all":
        print(f"ERROR: unknown command {sys.argv[1]!r}", file=sys.stderr)
        sys.exit(1)
    config_path = os.path.expanduser(sys.argv[2])
    targets_path = os.path.expanduser(sys.argv[3])
    with open(targets_path, "r", encoding="utf-8") as f:
        targets_in = json.load(f)
    targets = [(t["company_slug"], t["provider"]) for t in targets_in]
    outcomes = fetch_all(targets, config_path)
    per_provider, per_cp, per_pl = aggregate_outcomes(outcomes)
    print(
        json.dumps(
            {
                "outcome_count": len(outcomes),
                "per_provider_outcomes": per_provider,
                "per_company_provider": per_cp,
            },
            indent=2,
        )
    )
    sys.exit(0)

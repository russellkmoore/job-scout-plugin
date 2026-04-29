---
phase: 02-provider-protocol-greenhouse-dispatcher-observability
plan: 01
subsystem: ats
tags: [httpx, threading, semaphore, dispatcher, protocol, dataclass, concurrent.futures, runs.jsonl]

# Dependency graph
requires:
  - phase: 01-schema-migration-paths-foundational-cleanup
    provides: schema v=4 (Source/ATS Provider tracker columns); validate_runs_log + ensure_today_subdirs (runs.jsonl + ats_raw/ paths exist on disk); CON-04 venv install hint convention; sibling-script bootstrap pattern
provides:
  - "scripts/ats/ Python package with empty PROVIDERS registry (Plan 02-02 lands greenhouse)"
  - "Provider Protocol contract via typing.Protocol — duck-typed conformance, no inheritance"
  - "Canonical Listing dataclass with raise-loudly __post_init__ on missing required fields"
  - "Concurrent dispatcher: shared httpx.Client + ThreadPoolExecutor + per-provider Semaphore + 3-state outcomes + kill-switch"
  - "Append-only runs.jsonl writer with per-(company, provider) hit counts + per-provider field-completion telemetry"
  - "RunOutcome enum (single source of truth) shared between dispatcher.py and runs_log.py"
affects:
  - "Plan 02-02 (Greenhouse provider) — imports Provider/FetchResult/DetectionResult from base.py and Listing from normalize.py"
  - "Plan 02-03 (scout-run wiring) — imports fetch_all + aggregate_outcomes from dispatcher.py and append_run from runs_log.py"
  - "Phase 3 (scout-detect) — reuses DetectionStatus + DetectionResult from base.py"
  - "Phase 4 (remaining providers + JSON-LD) — register lever/ashby/smartrecruiters/workday into PROVIDERS; provider modules conform to the protocol"
  - "Phase 5 (cross-source dedup + tier bump) — reads runs.jsonl per_company_provider hit counts to detect ATS regression suspects"

# Tech tracking
tech-stack:
  added:
    - "httpx>=0.27,<0.29 (installed 0.28.1) — sync thread-safe Client; replaces no prior HTTP client (project previously used urllib only on the LinkedIn / state path)"
  patterns:
    - "typing.Protocol for duck-typed plug-in contracts (no inheritance burden)"
    - "Module-level _SEMAPHORES dict mutated in place (clear+update) so external imports see fresh state across fetch_all() calls"
    - "Two-tier exception handling: re-raise KeyboardInterrupt/MemoryError/SystemExit; bucket all other Exception as ERROR with structured stderr context"
    - "Append-only JSONL writer (open 'a' + flush, never read+rewrite)"
    - "Single-source-of-truth enum (RunOutcome lives in runs_log.py and is imported by dispatcher.py)"

key-files:
  created:
    - "scripts/ats/__init__.py — package marker, PROVIDERS registry, sibling-bootstrap docstring"
    - "scripts/ats/providers/__init__.py — providers package marker"
    - "scripts/ats/providers/base.py — Provider Protocol + DetectionResult/FetchResult/DetectionStatus"
    - "scripts/ats/normalize.py — frozen Listing dataclass + REQUIRED_FIELDS + compute_missing_fields helper"
    - "scripts/ats/runs_log.py — RunOutcome enum + append_run() + compute_field_completion() + CLI subcommand"
    - "scripts/ats/dispatcher.py — fetch_all, aggregate_outcomes, load_caps_and_kill_switch, _execute_one, _gate, _init_semaphores, FetchOutcome"
  modified: []

key-decisions:
  - "DSP-01 Provider Protocol via typing.Protocol with @runtime_checkable — no base class, no inheritance"
  - "DSP-02 Listing.__post_init__ raises ValueError on empty/None required field; field-completion telemetry in compute_missing_fields operates on dicts (not Listings) to count without crashing"
  - "DSP-03 Single shared httpx.Client per fetch_all() call, owned-vs-borrowed pattern via `client: Optional[httpx.Client] = None` parameter; closed in finally only when owned; httpx.Timeout(connect=5, read=15, write=15, pool=15) — write/pool added for httpx 0.28+ API requirement"
  - "DSP-04 ThreadPoolExecutor(max_workers=20) + module-level _SEMAPHORES (mutated in place via clear+update) so concurrent fetch_all() calls share the per-provider cap"
  - "DSP-05 RunOutcome enum (OK_WITH_RESULTS / OK_ZERO / ERROR) lives in runs_log.py — dispatcher.py imports it; single source of truth"
  - "DSP-06 _execute_one wrapper: re-raise KeyboardInterrupt/MemoryError/SystemExit; bucket all other Exception as ERROR with `f'{type(exc).__name__}: {exc}'` plus `ERROR: {provider}/{company}: {err}` to stderr; Future.result() always returns FetchOutcome (no swallowed Future.exception())"
  - "DSP-07 append_run() opens runs.jsonl in 'a' mode and flushes; never reads or rewrites; writes timestamp + wall_clock_seconds + per-provider counts (with field_completion sub-dict) + per_company_provider hit counts keyed `{slug}|{provider}`"
  - "DSP-08 ats.concurrency_disabled kill-switch: when true, fetch_all replaces ThreadPoolExecutor with a sequential list comprehension; same FetchOutcome shape; same _gate semaphore acquire/release (Semaphore(1) per provider)"
  - "Sibling-script bootstrap: 2-level dirname for scripts/ats/*.py (file → ats → scripts); 3-level for scripts/ats/providers/*.py (file → providers → ats → scripts); pattern documented in scripts/ats/__init__.py docstring"

patterns-established:
  - "Provider plug-in registration: per-provider module sets `from ats import PROVIDERS; PROVIDERS['name'] = SomeProvider` at import time. Plan 02-02 follows this for greenhouse."
  - "Stress-test verification (SC-5): a synthetic _StubProvider registered into PROVIDERS for the duration of an inline-Python verify, with `threading.Lock`-protected peak counter. No new tests/ file (per CLAUDE.md anti-feature: no general test suite)."
  - "Owned-vs-borrowed httpx.Client lifecycle (`owned_client = client is None`) so detect.py + dispatcher.py can later share a Client without double-close."

requirements-completed: [DSP-01, DSP-02, DSP-03, DSP-04, DSP-05, DSP-06, DSP-07, DSP-08]

# Metrics
duration: 8min
completed: 2026-04-29
---

# Phase 2 Plan 01: Provider Protocol + Dispatcher + Observability Substrate Summary

**ATS dispatcher substrate landed: 6 new files under `scripts/ats/` deliver typing.Protocol-based provider contract, raise-loudly Listing dataclass, concurrent fetch with per-provider semaphores, three-state outcome bucketing, append-only runs.jsonl writer with per-(company, provider) hit counts and field-completion telemetry, and a config-driven kill-switch — Plan 02-02 can now build greenhouse.py against published contracts with no scavenger hunt.**

## Performance

- **Duration:** ~8 min (plan start 2026-04-29T01:13:08Z; final commit 2026-04-29T01:21Z)
- **Started:** 2026-04-29T01:13:08Z
- **Completed:** 2026-04-29
- **Tasks:** 5 of 5 complete (Task 0 prerequisite + Tasks 1–4)
- **Files modified:** 6 created (scripts/ats/__init__.py, scripts/ats/providers/__init__.py, scripts/ats/providers/base.py, scripts/ats/normalize.py, scripts/ats/runs_log.py, scripts/ats/dispatcher.py)
- **Lines added:** 838 (248 + 174 + 416)

## Accomplishments

- **Substrate published before any provider exists.** The highest-risk decisions of the milestone (Listing shape, dispatcher concurrency model, Protocol contract, runs.jsonl schema) are all locked in before the cost of 5 providers — a refactor here is one day; a refactor after Phase 4 would be three.
- **SC-5 acceptance gate passed by direct observation.** Stress test against 30 synthetic targets with cap=10 produced peak observed concurrency = 10 (boundary hit, not vacuous serialization). DSP-04 semaphore enforcement verified, not just claimed.
- **runs.jsonl schema makes "trust ATS on 0/error" defensible from day one.** Per-(company, provider) hit counts plus field-completion telemetry are written from the very first run; Phase 5's regression-suspect detection has data to compare against.
- **Anti-features baked in.** Zero `import asyncio`, zero retry-on-403/429, zero Chrome-fallback hooks, zero worker-thread tracker writes. Every locked anti-decision is enforced by absence in the code, not just by docstring.

## Task Commits

Each substrate task was committed atomically:

1. **Task 0: Install httpx into verify venv** — *no commit* (one-time phase prerequisite, no source files changed); httpx 0.28.1 installed into `~/.job-scout-venv`.
2. **Task 1: Package skeleton + Provider Protocol + Listing** — `f2703c4` (feat) — 4 files, 248 lines.
3. **Task 2: runs_log.py append-only JSONL writer** — `123c3d5` (feat) — 1 file, 174 lines.
4. **Task 3: dispatcher.py with shared Client + semaphores + 3-state + kill-switch** — `54f8a61` (feat) — 1 file, 416 lines.
5. **Task 4: SC-5 semaphore stress test** — *no commit* (acceptance gate; no source files changed).

**Plan metadata commit:** `<this commit>` (docs: plan summary + state + roadmap update)

## Files Created/Modified

- `scripts/ats/__init__.py` (43 lines) — Package marker; `PROVIDERS: Dict[str, "Provider"] = {}` empty registry; module docstring documents the 1/2/3-level sibling-bootstrap dirname counts so future contributors don't have to count.
- `scripts/ats/providers/__init__.py` (1 line) — Providers package marker.
- `scripts/ats/providers/base.py` (115 lines) — `class Provider(Protocol)` (5-method shape: `NAME`, `BOARD_URL_PATTERNS`, `detect`, `board_url_from_url`, `fetch`, `to_listing`) with `@runtime_checkable`; frozen `DetectionResult` and `FetchResult` dataclasses; `DetectionStatus` enum (CONFIRMED / BORDERLINE / NOT_FOUND / ERROR). Forward-references `httpx`/`threading`/`Listing` via `TYPE_CHECKING` to avoid circular and hard-import dependencies.
- `scripts/ats/normalize.py` (89 lines) — Frozen `Listing` dataclass (6 required fields: company, title, location, url, posted_date, source; 4 optional: description, department, employment_type, raw); `__post_init__` raises ValueError on empty/None required field; `REQUIRED_FIELDS` tuple; `compute_missing_fields(listing_dict)` helper that operates on dicts to count without crashing.
- `scripts/ats/runs_log.py` (174 lines) — `RunOutcome` enum (single source of truth, imported by dispatcher.py); `append_run()` opens runs.jsonl in 'a' mode and flushes; `compute_field_completion()` per-required-field present-rate; CLI subcommand `append-run <runs_log_path> <stats.json>`. Uses 2-level sibling-script bootstrap.
- `scripts/ats/dispatcher.py` (416 lines) — `fetch_all()` public entry point with shared httpx.Client and `Optional[client]` owned-vs-borrowed lifecycle; `_execute_one()` two-tier exception wrapper; `_gate()` context manager around per-provider semaphore; `_init_semaphores()` mutates module-level `_SEMAPHORES` in place; `load_caps_and_kill_switch()` reads `config.json`'s `ats.provider_concurrency_caps` + `ats.concurrency_disabled`; `aggregate_outcomes()` reduces FetchOutcome list to the three dicts append_run() expects; `DEFAULT_PROVIDER_CAPS` matches research/STACK.md; `DEFAULT_TIMEOUT = httpx.Timeout(connect=5, read=15, write=15, pool=15)`; CON-04-compliant httpx ImportError install hint; CLI subcommand `fetch-all`.

## Decisions Made

- **httpx Timeout pinning of write/pool to 15s.** httpx 0.28+ requires either a `default` OR all four explicit (connect, read, write, pool). The locked decision was `connect=5, read=15`; I pinned write=15 and pool=15 so a slow tenant can't hang on upload (POST-style Workday) or pool-acquisition either. Documented inline in dispatcher.py.
- **`_SEMAPHORES` mutated in place rather than rebound.** The plan task action originally specified `global _SEMAPHORES; _SEMAPHORES = {...}`. I switched to `_SEMAPHORES.clear(); _SEMAPHORES.update({...})` so external imports via `from ats.dispatcher import _SEMAPHORES` see the new contents. Plain rebinding leaves external imports pointing at the now-orphaned old dict — that's exactly what the Task 3 verify caught.
- **Followed plan elsewhere as written.** Provider Protocol shape, Listing field set, RunOutcome enum location, kill-switch semantics, exception two-tier handling, semaphore-stress test — all match the plan's locked decisions verbatim.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] httpx 0.28+ Timeout API change**
- **Found during:** Task 3 verify (Python integration smoke).
- **Issue:** Plan task action specified `httpx.Timeout(connect=5.0, read=15.0)` but httpx 0.28+ requires either a `default` parameter OR all four (connect, read, write, pool) explicit. Module-import time raised `ValueError: httpx.Timeout must either include a default, or set all four parameters explicitly.` before the test could run.
- **Fix:** Added `write=15.0, pool=15.0` to the `DEFAULT_TIMEOUT` literal. Kept the locked `connect=5.0, read=15.0` so the verify grep (`httpx.Timeout(connect=5`) still matches and the substantive timeout decision is unchanged. Added 4-line inline comment explaining the API change.
- **Files modified:** `scripts/ats/dispatcher.py` (1 line + 4 lines of comment).
- **Verification:** Task 3 Python integration verify reran and printed `Task 3 OK`.
- **Committed in:** `54f8a61` (rolled into the same Task 3 commit; the file was created with the fix already applied after the first verify failure).

**2. [Rule 1 - Bug] `_SEMAPHORES` external-import staleness**
- **Found during:** Task 3 verify (`assert 'greenhouse' in _SEMAPHORES` failed after `_init_semaphores({'greenhouse': 10, 'lever': 5})`).
- **Issue:** Plan task action's `_init_semaphores` rebound the module global with `global _SEMAPHORES; _SEMAPHORES = {...}`. The verify imports `_SEMAPHORES` via `from ats.dispatcher import _SEMAPHORES`, which captures the *original* dict object at import time. Rebinding the module name leaves the imported reference pointing at the orphaned old dict, so the assertion saw an empty dict even though the module's `_SEMAPHORES` was correctly populated.
- **Fix:** Changed `_init_semaphores` to mutate the existing dict in place (`_SEMAPHORES.clear(); _SEMAPHORES.update({...})`) so external imports see the new contents. This is also more correct in production — any caller that imports `_SEMAPHORES` (Phase 3 detect.py is one candidate) won't end up with a stale reference.
- **Files modified:** `scripts/ats/dispatcher.py` (`_init_semaphores` body + docstring note).
- **Verification:** Task 3 verify reran and printed `Task 3 OK`; Task 4 stress test passed with peak=10 (would have stayed at peak≈10 in prod either way, but external imports — like the verify itself — now stay live).
- **Committed in:** `54f8a61` (same task commit).

---

**Total deviations:** 2 auto-fixed ([Rule 1 - Bug] × 2)
**Impact on plan:** Both auto-fixes were necessary for correctness (httpx 0.28 API + Python import semantics) and did not alter any locked decision. Net effect: dispatcher.py is more robust to in-process concurrent callers and forward-compatible with httpx 0.28+.

## Issues Encountered

- **None outside the two Rule-1 auto-fixes above.** All grep checks, Python integration smokes, plan-level verification (3 OK lines), and the SC-5 semaphore stress test passed without further intervention.

## User Setup Required

None. The plan's only user-facing prerequisite is httpx in the verify venv (Task 0), which the executor handled directly via `~/.job-scout-venv/bin/pip install 'httpx>=0.27,<0.29'`. End users hit the dispatcher.py ImportError install hint at runtime, which guides them through the same venv-based install or `pip install --user` alternative — exactly the CON-04 convention from Phase 1.

## Verify Results

The three plan-level verification lines all printed:

```
PLAN-LEVEL: 6 files OK
PLAN-LEVEL: requirements OK
PLAN-LEVEL: end-to-end empty roundtrip OK
```

Plus the SC-5 stress test:

```
Task 4 OK: semaphore enforces cap=10 against 30 concurrent calls (peak observed: 10)
```

Plus the compliance gates:

- `import asyncio` count in `scripts/ats/`: **0** (anti-feature honored)
- `--break-system-packages` count in `scripts/ats/`: **0** (CON-04 honored)
- `import rapidfuzz` count in `scripts/ats/`: **0** (rapidfuzz is Phase 5; only a docstring mention in `base.py:52` describing what `DetectionResult.confidence` will represent in Phase 3 + 5)
- `skills/scout-run/SKILL.md` modified count in plan commits: **0** (Plan 02-03 owns that)

## Hand-off to Plan 02-02 (Greenhouse Provider)

The substrate is ready. Plan 02-02's greenhouse.py imports the published contracts directly:

```python
from ats import PROVIDERS                              # for registration at module bottom
from ats.normalize import Listing                      # canonical listing shape
from ats.providers.base import (                       # protocol contract + result types
    Provider, FetchResult, DetectionResult, DetectionStatus,
)
```

**No scavenger hunt required.** The 5-method Provider shape is published in `base.py` line 95+; the Listing required-field set is published in `normalize.py:REQUIRED_FIELDS`; the FetchResult shape is published in `base.py` line 71+; and the dispatcher will already iterate `PROVIDERS.items()` and never name `'greenhouse'` directly — Plan 02-02 just needs to register at module bottom:

```python
PROVIDERS["greenhouse"] = GreenhouseProvider
```

**Sibling-script bootstrap for `scripts/ats/providers/greenhouse.py` is 3-level:**

```python
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# file → providers → ats → scripts
```

This is documented in the `scripts/ats/__init__.py` module docstring so Plan 02-02 doesn't have to count `dirname()` calls.

**Concurrency contract:** `provider.fetch(slug, client, semaphore)` is invoked WITH the semaphore already acquired (the dispatcher's `_gate` context manager wraps the call). The provider should NOT acquire the semaphore again — it's only passed in case the provider needs to spawn sub-fetches that should also be capped.

## Self-Check: PASSED

- All 6 created files exist on disk: `scripts/ats/{__init__.py, providers/__init__.py, providers/base.py, normalize.py, runs_log.py, dispatcher.py}` — `test -f` confirmed for each.
- All 3 task commits exist in git log:
  - `f2703c4` — feat(02-01): add scripts/ats package skeleton + Provider Protocol + Listing (DSP-01, DSP-02)
  - `123c3d5` — feat(02-01): add runs_log.py append-only JSONL writer with per-(company, provider) telemetry (DSP-05, DSP-07)
  - `54f8a61` — feat(02-01): add dispatcher with shared httpx.Client + per-provider semaphores + 3-state outcomes + kill-switch (DSP-03, DSP-04, DSP-05, DSP-06, DSP-08)
- All success criteria gates passed (asyncio=0, break-system-packages=0, rapidfuzz import=0, scout-run/SKILL.md untouched).

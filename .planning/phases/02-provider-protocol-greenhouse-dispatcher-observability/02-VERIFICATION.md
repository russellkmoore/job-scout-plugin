---
phase: 02-provider-protocol-greenhouse-dispatcher-observability
verified: 2026-04-29T02:00:00Z
status: passed
score: 5/5 success criteria + 10/10 DSP-* requirements verified
re_verification:
  is_re_verification: false
gaps: []
deferred:
  - truth: "User runs /scout-run against ≥3 known-Greenhouse companies AND sees Greenhouse listings appear under [ATS-PREVIEW] in the daily report (live network)"
    addressed_in: "Phase 3"
    evidence: "ROADMAP Phase 3 SC-1 + DET-06: /scout-detect populates ats_provider=\"greenhouse\" + ats_board_url for top-30 connection-weighted companies in master_targets.csv. Until that lands, master_targets.csv has no rows with ats_provider=greenhouse, so Step 2.5's slug list is empty and preview.py runs the 0-outcome heartbeat path. The end-to-end live-network listings-in-report demonstration is intentionally deferred to Phase 3 — Plan 02-03 SUMMARY explicitly calls this out (\"the [ATS-PREVIEW] block will start producing real network output starting in Phase 3, after /scout-detect populates ats_provider=\\\"greenhouse\\\" for top-30 companies in master_targets.csv\")."
human_verification: []
---

# Phase 2: Provider Protocol + Greenhouse + Dispatcher + Observability — Verification Report

**Phase Goal:** A user running `/scout-run` sees Greenhouse-sourced listings appearing in their daily report behind an `[ATS-PREVIEW]` tag, alongside the existing 3-pass flow, and can inspect per-company, per-provider counts in `runs.jsonl` from day one.

**Verified:** 2026-04-29T02:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## VERIFIED: PHASE 2 GOAL ACHIEVED

All 5 ROADMAP Success Criteria verified by live-codebase exercise. All 10 DSP-* requirements have concrete evidence in the live source. Every Phase 2 anti-feature gate honored. User's pending uncommitted edits preserved byte-identically.

---

## Success Criteria — One Line Per SC

| # | Success Criterion | Status | Evidence |
|---|---|---|---|
| SC-1 | Greenhouse listings tagged `[ATS-PREVIEW] source=ats:greenhouse` appear in report; existing 3-pass flow still present | PASSED (with one Phase-3-deferred sub-item) | `git show HEAD:skills/scout-run/SKILL.md` contains `## Step 2.5: [ATS-PREVIEW] Pass 1 (Greenhouse only) — additive` (line 110) and references `scripts/ats/preview.py` + `ats:greenhouse` literal source tag (4 occurrences); fixture roundtrip via `gh.to_listing(j)` produces 3 Listings each with `source='ats:greenhouse'`; existing Step 2 (Pass 1 company-first deep-dive) intact at line 78. **The live-network demonstration against ≥3 known-Greenhouse companies in master_targets.csv is deferred to Phase 3** because master_targets.csv currently has no `ats_provider=greenhouse` rows (Phase 3 `/scout-detect` populates them). The wiring is verified end-to-end via the empty-slugs roundtrip + fixture exercise. |
| SC-2 | `tail -1 runs.jsonl \| jq` shows wall_clock_seconds, per-provider counts (ok_with_results/ok_zero/error), per-(company, provider) listing counts, field-completion telemetry | PASSED | Synthetic `append_run` call writes line with `timestamp`, `wall_clock_seconds=12.345`, `providers.greenhouse.{ok_with_results=5, ok_zero=2, error=1, field_completion={posted_date=0.5, ...}}`, `per_company_provider={"airbnb\|greenhouse": {outcome: OK_WITH_RESULTS, listing_count: 3}, "lululemon\|greenhouse": {outcome: OK_ZERO, listing_count: 0}}`. Append-only verified: 2 sequential appends produced 2 lines (file not rewritten). |
| SC-3 | `ats.concurrency_disabled: true` flips next run to sequential without code change | PASSED | `load_caps_and_kill_switch(cfg)` reads kill=True from JSON; `fetch_all` enters sequential branch (line 299–313 of dispatcher.py) — list comprehension over `_execute_one`, no ThreadPoolExecutor; same `FetchOutcome` shape returned (verified with stub provider, 2 OK_ZERO outcomes). |
| SC-4 | Deliberately-broken Greenhouse fixture surfaces as logged exception in runs.jsonl with (company, provider) context | PASSED | `_BrokenGreenhouse` stub returning a Listing with empty `title` triggers `Listing.__post_init__` ValueError → caught by `_execute_one`'s Tier-2 `except Exception` → bucketed as `RunOutcome.ERROR` with `error="ValueError: Listing.title is required but was empty/None (company='X', source='ats:greenhouse'). Per-provider mapper must populate this — DSP-02."`, `company_slug='test-co'`, `provider='greenhouse'`. Stderr also logged: `ERROR: greenhouse/test-co: ValueError: Listing.title is required ...`. |
| SC-5 | 30 Greenhouse + 1 Lever stub → never >10 simultaneous Greenhouse connections (per-provider, not global) | PASSED | Stress test with `_StressGreenhouse` recording peak via `threading.Lock`-protected counter, 30 greenhouse + 1 lever targets, `max_workers=20`, caps={greenhouse: 10, lever: 5}: **peak observed = 10**, not 1 (real concurrency, not over-serialized) and not 11+ (cap enforced). Per-provider keying confirmed by separate `_StressLever` stub registered alongside. |

---

## DSP-* Requirements Coverage Audit

| DSP-ID | Description | Status | Evidence (file:line or smoke command + result) |
|---|---|---|---|
| DSP-01 | `Provider` Protocol with NAME, BOARD_URL_PATTERNS, detect, board_url_from_url, fetch, to_listing — duck-typed conformance | SATISFIED | `scripts/ats/providers/base.py:90` `class Provider(Protocol)` `@runtime_checkable`; `scripts/ats/providers/base.py:117–123` declares all 6 surfaces; `isinstance(PROVIDERS['greenhouse'], Provider) → True` (live verified). |
| DSP-02 | Canonical `Listing` dataclass + raise-loudly mappers on missing required fields | SATISFIED | `scripts/ats/normalize.py:24–69` frozen Listing dataclass; `__post_init__` raises ValueError listing the failing field name; `REQUIRED_FIELDS = ('company', 'title', 'location', 'url', 'posted_date', 'source')`; SC-4 smoke test confirms ValueError surfaces field name. |
| DSP-03 | One shared httpx.Client per run + httpx.Timeout(connect=5, read=15) | SATISFIED | `scripts/ats/dispatcher.py:83` `DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=15.0, pool=15.0)` (write/pool added for httpx 0.28+ API; locked connect/read intact); `dispatcher.py:317–324` instantiates one Client in fetch_all, owned-vs-borrowed via `client: Optional[httpx.Client] = None`; **SKILL boundary preserved:** `git show HEAD:skills/scout-run/SKILL.md \| grep -c 'fetch_all('` = **0** (preview.py is the single Bash call); `grep -c 'fetch_all(' scripts/ats/preview.py` = **1** (the actual call at line 130). |
| DSP-04 | ThreadPoolExecutor(max_workers=20) + per-provider Semaphore from config.json (defaults: greenhouse=10, ashby=8, lever=5, smartrecruiters=5, workday=3) | SATISFIED | `dispatcher.py:65–71` `DEFAULT_PROVIDER_CAPS` matches spec; `dispatcher.py:76` `DEFAULT_MAX_WORKERS = 20`; `dispatcher.py:327` `with ThreadPoolExecutor(max_workers=max_workers) as pool`; `dispatcher.py:143–157` `_init_semaphores` mutates module-level `_SEMAPHORES` dict in place (clear+update — important so external imports see fresh state). SC-5 stress test verified peak=10 against 30 simultaneous targets. |
| DSP-05 | Three-state outcome: OK_WITH_RESULTS / OK_ZERO / ERROR all logged separately | SATISFIED | `scripts/ats/runs_log.py:56–67` `RunOutcome` enum (single source of truth); `dispatcher.py:231–249` produces all three states; SC-2 telemetry shows separate counts per state. |
| DSP-06 | Worker exceptions surfaced not swallowed (two-tier: re-raise unrecoverable, bucket recoverable as ERROR with full context) | SATISFIED | `dispatcher.py:250–255` re-raises KeyboardInterrupt/MemoryError/SystemExit; `dispatcher.py:256–271` bucket-as-ERROR catch with stderr log `ERROR: {provider}/{company}: {type(exc).__name__}: {exc}` and FetchOutcome.error populated. SC-4 verified end-to-end. |
| DSP-07 | Append-only runs.jsonl writer per /scout-run with timestamp, wall_clock_seconds, per-provider counts, per-(company, provider) listing counts, field-completion telemetry | SATISFIED | `runs_log.py:90–143` `append_run` opens 'a' mode + flushes; never reads/rewrites; `runs_log.py:70–87` `compute_field_completion` produces per-required-field 0..1 rate; SC-2 smoke verified entire schema present + append-only behavior (2 sequential appends → 2 lines). |
| DSP-08 | `ats.concurrency_disabled: true` kill-switch falls back to sequential per-provider fetches | SATISFIED | `dispatcher.py:110–140` `load_caps_and_kill_switch` reads from config; `dispatcher.py:299–313` sequential list-comp branch when kill=True. SC-3 stress test verified end-to-end. |
| DSP-09 | greenhouse.py first conformant Provider; checked-in fixture under tests/fixtures/ats/greenhouse/ | SATISFIED | `scripts/ats/providers/greenhouse.py` (348 lines) NAME + 3 BOARD_URL_PATTERNS + LIST_URL_TEMPLATE + _strip_html (html.unescape→HTMLParser two-stage) + detect + board_url_from_url + fetch + to_listing; `scripts/ats/__init__.py:45–49` registers `PROVIDERS["greenhouse"] = _greenhouse_module`; fixture at `tests/fixtures/ats/greenhouse/airbnb.json` (26 KB, 3-job sanitized slice) + `SOURCE.md` provenance log. Live fixture roundtrip: 3 Listings parsed, all carry `source='ats:greenhouse'`. |
| DSP-10 | /scout-run Step 2 wired to ATS dispatcher additively under [ATS-PREVIEW] tag, writing to daily/<DATE>/ats_raw/ + visible in report | SATISFIED | `git show HEAD:skills/scout-run/SKILL.md` contains `## Step 2.5: [ATS-PREVIEW] Pass 1 (Greenhouse only) — additive` (line 110); references `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/preview.py` (line 129); `preview.py` orchestrates ats_raw/<provider>/<slug>.json persistence + `runs_log.append_run` in ONE process. **Existing Step 2 (Pass 1 company-first deep-dive) at line 78 is unchanged** — the additive contract holds. |

**All 10 of 10 Phase 2 requirements satisfied.**

---

## Special Verifications (anti-feature + invariant gates)

| Check | Expected | Actual | Status |
|---|---|---|---|
| `grep -r "import asyncio\|from asyncio" scripts/ats/` | 0 matches | 0 matches | PASSED (asyncio anti-feature honored) |
| `git diff 37c2bd3..HEAD --name-only \| grep -E 'requirements\.txt\|setup\.py\|pyproject\.toml'` | 0 matches | 0 matches | PASSED (no formal dependency manifest) |
| `find tests/ -name "test_*.py" -newer .planning/phases/02-...` | 0 matches | 0 matches | PASSED (only `tests/test_migration.py` from Phase 1; no new pytest files) |
| `git status --short skills/scout-run/SKILL.md` | ` M skills/scout-run/SKILL.md` | ` M skills/scout-run/SKILL.md` | PASSED (user's pending edits in working tree only) |
| `git diff skills/scout-run/SKILL.md` content | exactly 2 user hunks (frontmatter 0.3.1→0.3.3 + Step 2 LinkedIn URL pattern) | 2 user hunks, +9 −2 lines (`version: 0.3.3` + `f_C` rationale block) | PASSED (stash-replay protocol byte-identical preservation) |
| `git show HEAD:skills/scout-run/SKILL.md \| grep -c 'fetch_all('` | 0 (DSP-03 invariant 3) | 0 | PASSED (BLOCKER 3 fix held — preview.py is the only invocation point) |
| `grep -c 'fetch_all(' scripts/ats/preview.py` | ≤2 (gate threshold) | 1 (the actual call) | PASSED |
| `grep -rn -F -- '--break-system-packages' scripts/ats/` | 0 matches (CON-04) | 0 matches | PASSED |
| `grep -rn -F 'import rapidfuzz' scripts/ats/` | 0 matches (Phase 5 reservation) | 0 matches | PASSED |
| Sibling-bootstrap nesting `scripts/ats/providers/greenhouse.py` | 3 dirname calls (file → providers → ats → scripts) | `os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` at line 31 | PASSED |
| Sibling-bootstrap nesting `scripts/ats/dispatcher.py` | 2 dirname calls (file → ats → scripts) | line 51 — `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` | PASSED |
| Sibling-bootstrap nesting `scripts/ats/runs_log.py` | 2 dirname calls | line 50 — 2 dirname calls | PASSED |
| Sibling-bootstrap nesting `scripts/ats/preview.py` | 2 dirname calls | line 64 — 2 dirname calls | PASSED |
| Sibling-bootstrap nesting `scripts/ats/normalize.py` | N/A (does not import schema.py) | 0 dirname calls (correct — no schema imports) | PASSED |

---

## Behavioral Spot-Checks (live exercise)

| Behavior | Command | Result | Status |
|---|---|---|---|
| `preview.py --help` shows usage | `python3 scripts/ats/preview.py --help` | "Usage: ... <data_dir> <TODAY> <slugs_csv>" + "ONE process -> ONE fetch_all -> ONE httpx.Client -> ONE runs.jsonl append" | PASSED |
| `preview.py --version` | `python3 scripts/ats/preview.py --version` | "preview.py: Phase 2 DSP-10 driver, v0.4" | PASSED |
| Empty-slugs roundtrip end-to-end | `python3 scripts/ats/preview.py "$TEMPDIR" "2026-04-29" ""` | exit 0, prints JSON summary `{outcome_count: 0, ...}`, appends 1 line to `$TEMPDIR/runs.jsonl` matching DSP-07 schema | PASSED |
| Fixture-driven Listing roundtrip | `gh.to_listing(j)` over 3 fixture jobs | 3 Listings, each with `source='ats:greenhouse'`, all required fields populated | PASSED |
| Protocol conformance | `isinstance(PROVIDERS['greenhouse'], Provider)` with runtime_checkable | True | PASSED |

---

## Anti-Patterns Found

None. Phase 2 honors all locked anti-features:
- No asyncio
- No retry-on-403/429 (the dispatcher does not retry)
- No Chrome fallback in scripts/ats/
- No worker-thread tracker writes (dispatcher returns aggregated outcomes only)
- No generic ATS abstraction layer (each provider is a module, not a subclass)
- No third-party "universal ATS detector" libraries
- No requirements.txt / setup.py / pyproject.toml
- No new pytest files (only the pre-existing tests/test_migration.py from Phase 1; fixtures are JSON, not test_*.py)
- No `--break-system-packages` install hint anywhere in scripts/ats/

---

## Deferred Items (NOT blocking — addressed in Phase 3)

| # | Item | Addressed In | Evidence |
|---|---|---|---|
| 1 | Live-network demonstration: user with master_targets.csv containing ≥3 known-Greenhouse companies sees Greenhouse listings in their daily report | Phase 3 | ROADMAP Phase 3 SC-1 + DET-06: `/scout-detect` populates `ats_provider="greenhouse"` + `ats_board_url` for top-30 connection-weighted companies in `master_targets.csv`. Until Phase 3 ships, master_targets.csv has no rows with `ats_provider=greenhouse`, so Step 2.5's slug list is empty and `preview.py` runs the 0-outcome heartbeat path. Plan 02-03 SUMMARY explicitly notes this design: *"the [ATS-PREVIEW] block will start producing real network output starting in Phase 3, after /scout-detect populates ats_provider=\"greenhouse\" for top-30 companies."* The Phase 2 wiring is verified end-to-end via the empty-slugs roundtrip + fixture-driven Listing exercise; the live-network exercise is intentionally Phase 3's contract. |

This is informational only — Phase 2 substrate + wiring is complete.

---

## Re-verification Metadata

This is the initial verification of Phase 2. No previous VERIFICATION.md existed.

---

## Gaps Summary

**No gaps.** All 5 ROADMAP success criteria pass concrete live-codebase tests; all 10 DSP-* requirements have file:line evidence; all anti-feature gates clear; all invariant gates (DSP-03 SKILL boundary `grep -c 'fetch_all(' = 0`, sibling-bootstrap nesting, user's pending edits preservation) hold. Phase 3 may proceed.

The only Phase-2 promise that requires Phase 3 to demonstrate end-to-end is the live-network user-facing report rendering against real Greenhouse companies — and that dependency was an acknowledged design decision documented in Plan 02-03 SUMMARY ("the [ATS-PREVIEW] block will start producing real network output starting in Phase 3"). The Phase 2 substrate is complete: the dispatcher works, Greenhouse provider works, runs.jsonl heartbeat works, the SKILL invokes preview.py once per run, and the user's pending edits in `skills/scout-run/SKILL.md` are preserved byte-identically via the stash-replay protocol.

---

_Verified: 2026-04-29T02:00:00Z_
_Verifier: Claude (gsd-verifier)_

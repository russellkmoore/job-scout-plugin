---
gsd_state_version: 1.0
milestone: v0.4
milestone_name: milestone
status: executing
last_updated: "2026-04-29T03:32:42.936Z"
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 10
  completed_plans: 7
  percent: 70
---

# State: job-scout-plugin

**Last updated:** 2026-04-29 (post-Plan 02-03 execution; Phase 2 COMPLETE — 3/3 plans complete; all 10 DSP-* requirements landed)

## Project Reference

**What this is:** A Claude Code plugin (`job-scout`) that runs daily job-sourcing for the user. Two skills do the operational work — `/scout-setup` (one-time) and `/scout-run` (daily) — backed by a small Python utility layer in `scripts/` for deterministic operations.

**Core value:** A daily run reliably surfaces 5–15 actionable, well-matched job listings per top-connection company — without depending on fragile marketing-page scraping.

**Current milestone:** v0.4 — ATS-first job sourcing. Replace the failing marketing-page Chrome scraping path with structured ATS API queries (Greenhouse, Lever, Ashby, SmartRecruiters, Workday) plus a JSON-LD fallback.

**See:**

- `.planning/PROJECT.md` — full project context, requirements (validated/active/OOS), constraints, key decisions
- `.planning/REQUIREMENTS.md` — 51 v1 requirements with traceability to phases
- `.planning/ROADMAP.md` — 6-phase delivery plan with success criteria
- `.planning/research/SUMMARY.md` — reconciled research findings (HIGH confidence)
- `.planning/codebase/` — existing codebase mapping (architecture, structure, conventions, concerns)

## Current Position

Phase: 3 (Detection + scout-detect skill + lazy inline detect + dead-doc-ref cleanup) — EXECUTING
Plan: 1 of 3
**Phase:** 2 — Provider Protocol + Greenhouse + dispatcher + observability — **COMPLETE**
**Plan:** 3 of 3 complete (02-01 substrate done; 02-02 Greenhouse provider done; 02-03 [ATS-PREVIEW] wire-in done)
**Status:** Executing Phase 3

**Progress:** 2/6 phases complete

```
[x] Phase 1 — Schema migration + paths + foundational cleanup (13 reqs) — 4/4 plans complete
    [x] Plan 01-01 — schema.py v=4 + STATUS_VALUES + validate_runs_log/ensure_today_subdirs + venv install hints (SCH-01..04, CON-02, CON-04 sites 1-2 of 4)
    [x] Plan 01-02 — state.py perm hardening + LEGACY_DATA_DIRS deletion + consolidate_targets dead-block + mine_connections header guard + venv install hints sites 3-4 (CON-01, CON-03, CON-04 sites 3-4 of 4, CON-05 scripts/-side, CON-07)
    [x] Plan 01-03 — docs/skills schema sync (file-contract.md path entries SCH-06; companies_per_day SSOT to templates/config.json CON-06; scout-setup legacy-dir migration prompt CON-05 user-facing)
    [x] Plan 01-04 — migration round-trip pytest + phase-wide grep gate (SCH-05; verifies 19 grep invariants + pytest exit 0)
[x] Phase 2 — Provider Protocol + Greenhouse + dispatcher + observability (10 reqs) — 3/3 plans complete
    [x] Plan 02-01 — scripts/ats package + Provider Protocol + Listing + dispatcher (shared httpx.Client + per-provider semaphores + 3-state outcomes + kill-switch) + runs_log.py (DSP-01..08)
    [x] Plan 02-02 — Greenhouse provider conforming to Provider Protocol + airbnb 3-job sanitized fixture + SC-4 broken-fixture stress test (DSP-09)
    [x] Plan 02-03 — [ATS-PREVIEW] Pass 1 wire-in to /scout-run Step 2.5 via scripts/ats/preview.py (single-fetch_all driver) + runs.jsonl append + ats_raw/<provider>/<slug>.json persistence; stash-replay protocol preserved user's pending uncommitted edits (DSP-10)
[ ] Phase 3 — Detection + /scout-detect + lazy inline + dead-doc-ref cleanup (10 reqs)
[ ] Phase 4 — Remaining providers + JSON-LD + filtering (11 reqs)
[ ] Phase 5 — Cross-source dedup + tier bump + enrich + scoring/tracker cleanup (16 reqs)
[ ] Phase 6 — Run summary + delete legacy + milestone close + version/PII/post-run cleanup (12 reqs)
```

**Total v1 requirements:** 72 (51 ATS feature + 21 concerns cleanup, surgically distributed into Phases 1/3/5/6).

## Milestone Bar (verification gate for Phase 6)

A v0.4 release is "done" only when all four are simultaneously true, verified from `<data_dir>/runs.jsonl`:

1. 5-run rolling Pass-1 (ATS) share ≥ 60% of A/B-tier candidates
2. `/scout-run` wall-clock ≤ 5 minutes (5-run average)
3. Zero references to marketing-page Chrome scraping in `skills/` or `scripts/`
4. Every listing in `report.md` carries a `source=` tag

## Performance Metrics

Tracked via `<data_dir>/runs.jsonl` once Phase 2 ships. Until then:

| Metric | Baseline (v0.3.3) | Target (v0.4) |
|--------|-------------------|---------------|
| Pass-1 share of A/B-tier | unknown / collapsed to LinkedIn-only | ≥60% (5-run rolling) |
| `/scout-run` wall-clock | 10–15 min | ≤5 min (5-run avg) |
| Marketing-page scraping calls | non-zero | 0 |
| Listings missing `source=` tag | 100% | 0% |

## Accumulated Context

### Decisions Locked (from PROJECT.md + research SUMMARY.md)

| Decision | Rationale |
|----------|-----------|
| ATS providers in v0.4: Greenhouse, Lever, Ashby, SmartRecruiters, Workday | ~80% coverage of top-connection companies; the easiest five public APIs |
| Hybrid detection: top-30 batch via `/scout-detect`, lazy inline for the rest | Balances upfront work for high-value targets vs. per-company effort |
| New `/scout-detect` skill (not inlined into `/scout-setup`) | Reusable when companies are added later |
| Pass 1 first, Pass 2 dedupes against Pass 1 | ATS is canonical; LinkedIn is supplemental |
| Dedupe key: company-slug + normalized-title fuzzy match (rapidfuzz) | Simple, fast, good enough for v0.4 |
| Dedupe band: ≥95% auto-merge, 70–95% review, <70% keep both | Avoids both under- and over-merging — both fail silently |
| Two-key dedupe: loose (slug + first-3-tokens) + tight (slug + full title); both must agree to auto-merge | Defense-in-depth against title noise |
| ATS-sourced jobs get +1 tier bump only when posted ≤30d ago | Stale ATS hits are not stronger signal than fresh LinkedIn |
| Enrich-then-tier for ATS A-candidates (LinkedIn shared-connection lookup) | Restores warm-path signal lost by pure ATS results |
| Trust ATS on 0/error (no Chrome fallback) | Milestone-defining decision; honesty over coverage |
| Concurrent ATS calls with per-provider semaphore caps from `config.json` | Bound load per provider; tunable without code change |
| Delete marketing-page Chrome scraping path entirely (not flag-and-keep) | Removing fragility is part of the milestone definition |
| Schema: `MASTER_TARGETS_VERSION` bumps to 4 with additive `ats_slug_confidence` + `last_ats_hit_date` columns | Per user choice in research reconciliation #1 |
| Stack: `httpx>=0.27,<0.29` (sync, thread-safe) + `rapidfuzz` + stdlib `concurrent.futures` + `threading.Semaphore` | `requests.Session` is not thread-safe; threading beats async at ~30 concurrent requests |
| Per-provider concurrency caps (initial): Greenhouse=10, Ashby=8, Lever=5, SmartRecruiters=5, Workday=3 | Derived from observed latency + tenant-isolation patterns; tunable in `config.json` |
| Two-factor detection gate: 200 + ≥1 job + name fuzzy match ≥85% (rapidfuzz `token_set_ratio`) | Prevents wrong-company false positives + wildcard catch-alls |
| Dispatcher distinguishes `OK_WITH_RESULTS` / `OK_ZERO` / `ERROR` | Without three states, "trust on zero" silently buries provider regressions |
| `runs.jsonl` carries per-(company, provider) hit counts + field-completion telemetry from Phase 2 onward | Makes trust-on-zero defensible from day one |
| `ats.concurrency_disabled: true` kill-switch in `config.json` | Sequential fallback without code change if concurrency misbehaves |

### Skills/Conventions to Honor (from codebase mapping)

- **Single source of truth** — schemas in `scripts/schema.py`, file paths in `skills/job-scout/references/file-contract.md`. Never duplicate.
- **Sibling-script bootstrap** — every script that imports from `schema.py` uses the `SCRIPTS_DIR` / `sys.path.insert(0, SCRIPTS_DIR)` block. Phase 2 `scripts/ats/*` modules must follow.
- **`try / except ImportError` pip hint** — every third-party dependency (httpx, rapidfuzz) surfaces the exact `pip install --break-system-packages` command on import failure.
- **Validators return `(ok, message)` tuples** — `validate_data.py` extensions must follow the existing pattern.
- **Plain `print()` for logging** — no `logging` module. Human-readable to stdout, errors to stderr with `ERROR:` prefix, machine-consumable JSON as the LAST `print()` of the CLI.
- **CLI subcommand dispatch via `sys.argv[1]`** — `scripts/ats/detect.py` follows the existing `tracker_utils.py` / `state.py` shape.
- **Schema migration must bump `MASTER_TARGETS_VERSION`** — and the migration code lives in `validate_data.py`. (Phase 1 enforces this.)
- **`os.path.expanduser()` at the boundary** — every CLI expands `~` exactly once when accepting paths.
- **All tracker writes go through `tracker_utils.py`** — never write `JobScout_Tracker.xlsx` from any other module. Worker threads do NOT call `tracker_utils.append_rows`.

### Pre-existing Concerns (from `.planning/codebase/CONCERNS.md`)

- Existing scraping logic is duplicated across boards — Phase 4 must NOT introduce a 6th copy of the per-source pattern. Provider Protocol + registry from Phase 2 absorbs all variation.
- LinkedIn JD lazy-load is fragile — Phase 5 reduces dependency on it (only ATS A-candidates need Chrome enrichment).
- The plugin has no test suite — v0.4 carve-out is `tests/test_migration.py` (Phase 1) + per-provider fixture tests (Phases 2 and 4). Not a broader test suite.
- `_write_tracker` rebuilds the entire xlsx on every append — known fragility, deferred to v0.5+ (PERF-03 in v2 requirements).

### Open Items (deferred to plan-phase)

- Phase 1 planning needs to confirm whether the v3→v4 migration can be done in `validate_data.py` as a pure additive append, or whether ordering needs an explicit branch.
- Phase 2 planning needs to confirm exact `httpx` version pin and the `tests/fixtures/ats/greenhouse/<company>.json` capture procedure.
- Phase 4 planning is flagged for deeper research per SUMMARY.md ("Workday is the most failure-prone provider — three known tenants need fixture capture; CSRF/auth-required detection requires careful 401/403 body inspection"). Recommend `/gsd-research-phase` before Phase 4 begins.
- Phase 5 planning is flagged for deeper research per SUMMARY.md ("dedup threshold tuning will need real Pass 1 + Pass 2 overlap data; revisit thresholds after first week of v0.4 runs").

### Blockers

None at roadmap stage.

## Session Continuity

**Last session ended:** 2026-04-29 — Plan 02-03 executed ([ATS-PREVIEW] wire-in to /scout-run Step 2.5 via scripts/ats/preview.py single-fetch_all driver; runs.jsonl append + ats_raw/<provider>/<slug>.json persistence; DSP-10 landed). **Phase 2 CLOSED OUT — all 10 DSP-* requirements complete.** User's 2 pending uncommitted hunks in skills/scout-run/SKILL.md (frontmatter version 0.3.3 + Step 2 LinkedIn URL pattern with f_C-disabled rationale) preserved byte-identical via the same stash-replay protocol Plan 01-03 used.

**Plan 02-03 deliverables (this session):**

- `scripts/ats/preview.py` — 221-line thin driver script: ONE process invocation per /scout-run; sibling-bootstrap (2-level); imports fetch_all + aggregate_outcomes from ats.dispatcher and append_run + RunOutcome from ats.runs_log; defines run_preview(data_dir, today, slugs, provider="greenhouse") -> dict; CLI dispatch (--help / --version / positional args); exits 0 on success, 2 on missing config.json, 1 on bad args. Verified: grep -c 'fetch_all(' = 1 (the actual call). Empty-slugs roundtrip appends exactly ONE runs.jsonl line + writes ZERO ats_raw files (commit 1de5157).
- `skills/scout-run/SKILL.md` — +50 lines; new ## Step 2.5: [ATS-PREVIEW] Pass 1 (Greenhouse only) — additive section between existing Step 2 and Step 3; documents slug-derivation + ONE Bash call to preview.py + report-rendering pattern; references preview.py + runs_log.append_run + ats_raw paths. Verified: grep -c 'fetch_all(' in committed SKILL.md = 0 (DSP-03 invariant at the SKILL boundary). User's 2 pending uncommitted hunks preserved verbatim (commit f562cca).
- SUMMARY at `.planning/phases/02-provider-protocol-greenhouse-dispatcher-observability/02-03-wire-preview-SUMMARY.md`

**Auto-fixed deviations during execution:** 1 × Rule 1 bug — preview.py's verbatim docstring opener contained 4 `fetch_all(` paren mentions (3 prose + 1 actual call), exceeding the threat-model verify gate of `grep -c 'fetch_all(' <= 2`. Reworded docstring + --help prose to use `fetch_all` (no paren) where it's documentation, kept paren only on the actual call at line 130. Behavior unchanged. Rolled into commit 1de5157 (Task 1). Documented in SUMMARY's Deviations section.

**Stash-replay protocol post-mortem:** Plan 01-03's protocol was applied a second time successfully against the same file. Snapshot to /tmp → reset to HEAD → apply edit → commit on clean base → restore snapshot to working tree → re-apply edit on top → cleanup /tmp. Final-state diff: working tree = HEAD + user's 2 pending hunks (byte-identical to pre-Task-2 snapshot). The `## Step 3: Pass 2 — Other job boards (≈25% of budget)` heading is the load-bearing anchor (identical in HEAD and snapshot). Pattern is now established and reproducible.

**Phase 2 closeout.** All 3 plans complete; all 10 DSP-* requirements landed (DSP-01..08 in Plan 02-01, DSP-09 in Plan 02-02, DSP-10 in Plan 02-03). The substrate is auditable from day one: any /scout-run invokes preview.py exactly once, opens ONE httpx.Client, writes ONE runs.jsonl heartbeat line. When /scout-detect (Phase 3) populates `ats_provider="greenhouse"` for top-30 companies, the [ATS-PREVIEW] block immediately starts producing real Greenhouse listings tagged in the daily report. Phase 5 will hoist the [ATS-PREVIEW] code path into Pass 1 anchor + apply +1 ATS tier bump.

**Plan 02-02 deliverables (prior session):**

- `tests/fixtures/ats/__init__.py` + `tests/fixtures/ats/greenhouse/__init__.py` — empty package markers (commit 1c9d270)
- `tests/fixtures/ats/greenhouse/airbnb.json` — sanitized 3-job slice from `boards-api.greenhouse.io/v1/boards/airbnb/jobs?content=true` (224 jobs total at capture; first 3 sliced) (commit 1c9d270)
- `tests/fixtures/ats/greenhouse/SOURCE.md` — fixture provenance + re-capture command + sanitization-log table (no redactions required for airbnb's public response) (commit 1c9d270)
- `scripts/ats/providers/greenhouse.py` — first conformant Provider Protocol implementation; module-level NAME, BOARD_URL_PATTERNS, detect, board_url_from_url, fetch, to_listing; html.unescape+HTMLParser two-stage stripping for entity-encoded `content` field; 3-level sibling-bootstrap; conditional httpx import (commit f358454)
- `scripts/ats/__init__.py` — PROVIDERS registry now contains 'greenhouse' via relative import (`from .providers import greenhouse as _greenhouse_module`); registers MODULE not instance for duck-typed Protocol conformance (commit 31d3762)
- SC-4 broken-fixture stress test passed: synthetic `_BrokenGreenhouse` stub bypasses greenhouse.fetch's per-job try/except, ValueError propagates to `_execute_one`, bucketed as ERROR with 'title' in error message; broken fixture cleaned up (Task 4 — no commit, no tracked artifacts)
- SUMMARY at `.planning/phases/02-provider-protocol-greenhouse-dispatcher-observability/02-02-greenhouse-SUMMARY.md`

**Auto-fixed deviations during execution:** 1 × Rule 1 bug — Greenhouse `content` is HTML-ENTITY-ENCODED HTML (`&lt;p&gt;...` not `<p>...`). Plan task action's `_strip_html` fed content directly to HTMLParser, which would leave entity-encoded tags as literal text in Listing.description (and the `'<' not in description` smoke assertion would PASS spuriously because there are no real `<` chars in encoded form). Fix: html.unescape FIRST, then HTMLParser. Rolled into commit f358454 (Task 2). Documented in SUMMARY's Deviations section.

**Plan 02-01 deliverables (prior session):**

- `scripts/ats/__init__.py` — package marker + `PROVIDERS: Dict[str, "Provider"] = {}` empty registry + 1/2/3-level sibling-bootstrap docstring (commit f2703c4)
- `scripts/ats/providers/__init__.py` — providers package marker (commit f2703c4)
- `scripts/ats/providers/base.py` — `class Provider(Protocol)` (5-method shape, `@runtime_checkable`) + frozen `DetectionResult`/`FetchResult` dataclasses + `DetectionStatus` enum (commit f2703c4)
- `scripts/ats/normalize.py` — frozen `Listing` dataclass with `__post_init__` raising on empty required fields + `REQUIRED_FIELDS` tuple + `compute_missing_fields` helper (commit f2703c4)
- `scripts/ats/runs_log.py` — `RunOutcome` enum (single source of truth) + `append_run()` (open 'a' + flush, never read+rewrite) + `compute_field_completion()` + CLI subcommand (commit 123c3d5)
- `scripts/ats/dispatcher.py` — `fetch_all` with shared httpx.Client + ThreadPoolExecutor(max_workers=20) + per-provider `_SEMAPHORES` + 3-state `FetchOutcome` + 2-tier exception wrapper + `ats.concurrency_disabled` kill-switch + `aggregate_outcomes` helper (commit 54f8a61)
- httpx 0.28.1 installed into `~/.job-scout-venv` (Task 0 prerequisite — no commit)
- SC-5 stress test passed: 30 stub targets / cap=10 → peak observed = 10 (Task 4 — no commit)
- SUMMARY at `.planning/phases/02-provider-protocol-greenhouse-dispatcher-observability/02-01-dispatcher-SUMMARY.md`

**Auto-fixed deviations during execution:** 2 × Rule 1 bugs in dispatcher.py both rolled into commit 54f8a61 — (a) httpx 0.28+ Timeout API requires write/pool params (added write=15, pool=15); (b) `_init_semaphores` rebound the global rather than mutating in place, leaving external imports stale (changed to `clear()` + `update()`). Both noted in SUMMARY's Deviations section.

**Plan 01-01 deliverables (prior session):**

- `scripts/schema.py` v=4 (commit 856d170)
- `scripts/validate_data.py` validators + venv hint (commits 77fb7b7, 9e6546f)
- `scripts/tracker_utils.py` status validation + 16-col rows + venv hint (commit 3b86340)
- SUMMARY at `.planning/phases/01-schema-migration-paths-foundational-cleanup/01-01-schema-SUMMARY.md`

**Plan 01-02 deliverables (prior session):**

- `scripts/consolidate_targets.py` install hint + dead summary block deletion (commits 0ab2447, 8346145)
- `scripts/state.py` `_harden_perms` + LEGACY_DATA_DIRS deletion (commit 8a74ba2)
- `scripts/mine_connections.py` install hint + header-detection guard + post-skip column validation (commits 0ab2447, 2b959c9)
- SUMMARY at `.planning/phases/01-schema-migration-paths-foundational-cleanup/01-02-cleanup-SUMMARY.md`

**CON-04 partition closed.** All four `--break-system-packages` sites are now venv/--user copy across both Wave-1 plans (validate_data.py + tracker_utils.py from Plan 01-01; consolidate_targets.py + mine_connections.py from Plan 01-02). Plan 01-04's grep gate has clean ground.

**Architectural item still flagged for Phase 5:** Pre-existing `"Stale — Verify"` status string in `tracker_utils.py:203` is warn-coerced to `"Active"` by the STATUS_VALUES validator (Plan 01-01). Non-data-destructive but loses the user-facing stale flag. Phase 5 tracker cleanup owns resolution.

**Plan 01-03 deliverables (prior session):**

- `skills/job-scout/references/file-contract.md` — added `runs.jsonl` row to Persistent files table + `daily/<DATE>/ats_raw/` row to Per-run output table (commit 9c13181)
- `skills/scout-run/SKILL.md` — line 73 inline `(default 8)` removed, replaced with prose pointing at `templates/config.json` (commit 2e84994; user's pre-existing uncommitted edits to lines 5 + 80-93 preserved untouched)
- `skills/job-scout/references/search-config.md` — line 43 inline `(default 8 in older configs, default 5 in template)` removed, replaced with prose pointing at `templates/config.json` (commit 2e84994)
- `skills/scout-setup/SKILL.md` — Step 1 question 4 inserted: detects 3 v0.3 legacy paths, prompts reuse, calls `state.py write` inline; original question 4 renumbered to 5 (commit 89971d4)
- SUMMARY at `.planning/phases/01-schema-migration-paths-foundational-cleanup/01-03-docs-SUMMARY.md`

**CON-05 user-facing closeout.** Plan 01-02 deleted `LEGACY_DATA_DIRS` from `scripts/state.py` (scripts side); Plan 01-03 added the user-facing `/scout-setup` Step 1 prompt that detects + reuses legacy data dirs by calling `state.py write` inline. Together: existing v0.3 users get a graceful upgrade path on first re-run of `/scout-setup`, and a fresh v0.4 user with no legacy dirs falls through to the existing fresh-setup flow.

**Plan 01-04 deliverables (prior session):**

- `tests/__init__.py` — empty package marker (commit a4e1abf)
- `tests/fixtures/master_targets_v3.csv` — checked-in v=3 fixture, 4 lines, 12 columns, 3 rows incl. user-added `my_notes` (commit a4e1abf)
- `tests/test_migration.py` — pytest module with 5 SCH-05 round-trip assertions; sibling-bootstrap import; `migrated_data_dir` fixture isolates each test in `tmp_path` (commit 6103fa8)
- Phase-wide grep gate verified — 19 grep checks + pytest exit 0; `PHASE 1 GATE: ALL CHECKS PASSED` (Task 3 verification-only, no commit)
- SUMMARY at `.planning/phases/01-schema-migration-paths-foundational-cleanup/01-04-migration-test-SUMMARY.md`

**Pytest install footnote.** pytest 9.0.3 was installed into the existing `~/.job-scout-venv` (which already had pandas 3.0.2). Test runs use `~/.job-scout-venv/bin/python3 -m pytest tests/test_migration.py --tb=short -q`. Module docstring carries CON-04-compliant install hint (`pipx install pytest` recommended; venv as fallback).

**Phase 1 closeout.** All 4 plans complete; all 13 Phase 1 requirements (SCH-01..06, CON-01..07) verified by the phase-wide grep gate. The gate is a single bash pipeline that re-runs in <5 seconds — phase-completion verifier can use it directly. Test infrastructure (tests/ + tests/fixtures/ layout, sibling-bootstrap pattern, exit-code gating) established for Phase 2 + 4 to reuse.

**Next action:** Begin Phase 3 — Detection + /scout-detect skill + lazy inline detect + dead-doc-ref cleanup (DET-01..07 + DOC-01). ROADMAP.md flags Phase 3 for `/gsd-research-phase` BEFORE planning: the two-factor detection gate's tuning (200 + ≥1 job + name fuzzy match ≥85%) needs real data from a top-30 batch run. Recommended sequence: `/gsd-research-phase 3` → `/gsd-discuss-phase 3` → `/gsd-plan-phase 3` → `/gsd-execute-phase 3`. Phase 3 builds on Phase 2's substrate — `PROVIDERS["greenhouse"].detect(slug, name, client)` is callable; the dispatcher + runs.jsonl writer + preview.py driver are wired into /scout-run additively.

**On resume, read in order:**

1. This file (`.planning/STATE.md`) for current position
2. `.planning/phases/02-provider-protocol-greenhouse-dispatcher-observability/02-03-wire-preview-SUMMARY.md` for the most recent plan context (Phase 2 closeout + DSP-10 wire-in)
3. `.planning/phases/02-provider-protocol-greenhouse-dispatcher-observability/02-02-greenhouse-SUMMARY.md` for Greenhouse provider context
4. `.planning/phases/02-provider-protocol-greenhouse-dispatcher-observability/02-01-dispatcher-SUMMARY.md` for the substrate context (dispatcher + runs_log + Provider Protocol)
5. `.planning/ROADMAP.md` Phase 3 section for the next phase's success criteria + flag for `/gsd-research-phase`

---
*Plan 02-03 executed: 2026-04-29 by sequential executor agent. Plan 02-02 executed: 2026-04-29. Plan 02-01 executed: 2026-04-29. Plan 01-04 executed: 2026-04-28. Plan 01-03 executed: 2026-04-28. Plan 01-02 executed: 2026-04-28. Plan 01-01 executed: 2026-04-28. State initialized: 2026-04-27 by /gsd-new-project (roadmapper).*

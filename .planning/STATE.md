# State: job-scout-plugin

**Last updated:** 2026-04-28 (post-Plan 01-01 execution)

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

**Phase:** 1 — Schema verification + paths + migration smoke-test
**Plan:** 01-01 complete (schema v=4 + STATUS_VALUES + validators + venv install hints); 01-02, 01-03, 01-04 remaining
**Status:** Phase 1 in progress — Plan 01-01 of 4 complete

**Progress:** 0/6 phases complete (1/4 plans in Phase 1 complete)

```
[~] Phase 1 — Schema migration + paths + foundational cleanup (13 reqs) — 1/4 plans complete
    [x] Plan 01-01 — schema.py v=4 + STATUS_VALUES + validate_runs_log/ensure_today_subdirs + venv install hints (SCH-01..04, CON-02, CON-04 sites 1-2 of 4)
    [ ] Plan 01-02 — file-contract.md paths + sister CON-04 sites
    [ ] Plan 01-03 — docs/skills schema sync
    [ ] Plan 01-04 — migration smoke-test + grep gates
[ ] Phase 2 — Provider Protocol + Greenhouse + dispatcher + observability (10 reqs)
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

**Last session ended:** 2026-04-28 — Plan 01-01 executed (schema.py v=4, STATUS_VALUES + helper, validate_runs_log/ensure_today_subdirs, tracker_utils status validation + 16-col rows, venv install hints in validate_data.py + tracker_utils.py).

**Plan 01-01 deliverables:**
- `scripts/schema.py` v=4 (commit 856d170)
- `scripts/validate_data.py` validators + venv hint (commits 77fb7b7, 9e6546f)
- `scripts/tracker_utils.py` status validation + 16-col rows + venv hint (commit 3b86340)
- SUMMARY at `.planning/phases/01-schema-migration-paths-foundational-cleanup/01-01-schema-SUMMARY.md`

**Architectural item flagged for Phase 5:** Pre-existing `"Stale — Verify"` status string in `tracker_utils.py:203` is now warn-coerced to `"Active"` by the new `STATUS_VALUES` validator. Non-data-destructive (row still written, stderr WARNING) but loses the user-facing stale flag. Three resolution paths possible — defer to Phase 5 tracker cleanup. See SUMMARY Deviation 2.

**Next action:** Execute Plan 01-02 (file-contract.md paths + sister CON-04 sites in `consolidate_targets.py` and `mine_connections.py`).

**On resume, read in order:**
1. This file (`.planning/STATE.md`) for current position
2. `.planning/phases/01-schema-migration-paths-foundational-cleanup/01-01-schema-SUMMARY.md` for completed plan context
3. `.planning/phases/01-schema-migration-paths-foundational-cleanup/01-02-cleanup-PLAN.md` for next plan
4. `.planning/ROADMAP.md` for the phase definition + success criteria

---
*Plan 01-01 executed: 2026-04-28 by sequential executor agent. State initialized: 2026-04-27 by /gsd-new-project (roadmapper).*

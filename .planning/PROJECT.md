# job-scout-plugin

## What This Is

A Claude Code plugin (`job-scout` v0.3.3) that runs daily job-sourcing for the user. Two skills do the operational work — `/scout-setup` (one-time) and `/scout-run` (daily) — backed by a small Python utility layer in `scripts/` for deterministic operations (schema, state pointer, tracker formatting, dedup, profile mining). The output is a daily report of A/B/C-tier listings with on-demand tailored resume + outreach packets.

## Core Value

A daily run reliably surfaces 5–15 actionable, well-matched job listings per top-connection company — without depending on fragile marketing-page scraping.

## Requirements

### Validated

<!-- Inferred from existing v0.3.3 codebase. -->

- ✓ User runs `/scout-setup` once to create config, candidate profile, master targets, tracker, and honest assessment — existing
- ✓ User runs `/scout-run` daily to produce a tiered report — existing
- ✓ Three-pass search budget (career pages → niche boards → LinkedIn keyword) — existing, being replaced
- ✓ Output written to `<data_dir>/daily/<DATE>/` with `report.md`, `run_log.json`, `new_rows.json` — existing
- ✓ On-demand packets generated when user replies `pack <id1> <id2>` — existing
- ✓ Deterministic schema/tracker/dedup factored into `scripts/` — existing
- ✓ State pointer at `~/.job-scout/state.json` survives `git pull` — existing
- ✓ Per-board search via Built In Seattle / Wellfound / YC / HN as Pass 2 — existing
- ✓ LinkedIn JD extraction via Claude in Chrome MCP — existing (recently fixed in v0.2.1)

### Active

**v0.4 — ATS-first job sourcing.** Replace fragile marketing-page scraping with structured ATS API queries.

- [ ] Pass 1 queries public ATS JSON APIs (Greenhouse, Lever, Ashby, SmartRecruiters, Workday) instead of marketing career pages
- [ ] New `/scout-detect` skill auto-detects ATS provider for the top-30 companies in `master_targets.csv` and writes `ats_provider` + `ats_board_url` back to the CSV (also reusable when companies are added)
- [ ] Hybrid detection model: top-30 detected once via `/scout-detect`; remaining companies use lazy inline detection during `/scout-run` (cached on success)
- [ ] Schema in `scripts/schema.py` extends `MASTER_TARGETS_COLUMNS` with `ats_provider` and `ats_board_url`
- [ ] Pass 1 (ATS) runs first; Pass 2 (LinkedIn keyword) runs second and dedupes against Pass 1 by company-slug + normalized-title fuzzy match
- [ ] ATS APIs are called concurrently with a per-provider concurrency cap (no fixed sleep between requests)
- [ ] If an ATS endpoint returns 0 jobs or errors, treat it as "no openings, move on" — no Chrome scrape fallback
- [ ] ATS-sourced jobs get a +1 tier bump in scoring (warm-path + structured-data signal)
- [ ] For ATS-sourced A-tier candidates, look up shared-connection enrichment via LinkedIn before final tier assignment
- [ ] ATS JSON description is used directly for matching/scoring — Chrome is NOT called for ATS-sourced JDs
- [ ] Existing Chrome-based marketing-page scraping path is **deleted** (not flagged, not kept as Pass 3)
- [ ] Each listing in `report.md` is tagged with `source=ats|linkedin` (and ATS provider where applicable)
- [ ] `/scout-run` prints a summary block at end: total jobs, A/B counts, Pass 1 share %, wall-clock time
- [ ] A persisted `<data_dir>/runs.jsonl` records one JSON line per run with counts/ratios/timings (enables trend tracking)
- [ ] Daily scheduled run produces a report where Pass 1 contributes ≥60% of A/B-tier candidates
- [ ] Total `/scout-run` wall-clock stays under 5 minutes (currently 10–15)
- [ ] Chrome is used **only** for LinkedIn JDs and shared-connection enrichment — never for career-page scraping

### Out of Scope

- **Greenhouse/Lever/Ashby/SmartRecruiters/Workday only** — Jobvite and Taleo deferred to v0.5+ (lower coverage, messier APIs)
- **Marketing-page scraping fallback** — explicitly removed; the user accepts that ATS-undetected companies fall through to Pass 2 (LinkedIn keyword) only
- **Per-provider rate-limit strategies** — start with a single concurrent-cap policy across all providers; specialize only if we discover real limits in production
- **Canonical-URL dedupe via redirect resolution** — not in v0.4; fuzzy company+title is good enough for now (revisit if false-merges become a problem)
- **Workday auth/CSRF complexity** — if a tenant requires session/CSRF tokens beyond the public POST endpoint, that company falls through to Pass 2 in v0.4
- **Tests as a deliverable** — the plugin still has no formal test suite; v0.4 will validate via real `/scout-run` invocations and the persisted run log, not unit tests
- **Mobile/web UI for the report** — output remains markdown in `<data_dir>/daily/<DATE>/`

## Context

**Codebase state.** Mapped in `.planning/codebase/`. Key facts:

- Skills (`SKILL.md`) hold control-flow + LLM judgement; `scripts/` (Python 3.8+) hold determinism (schemas, tracker formatting, dedup, state pointer)
- Single-source-of-truth: `scripts/schema.py` defines `MASTER_TARGETS_COLUMNS`; `skills/job-scout/references/file-contract.md` defines every path
- Plugin path: `${CLAUDE_PLUGIN_ROOT}` env var resolves all internal references
- User data lives outside the plugin in `~/Documents/JobSearch/` (so `git pull` never touches it)
- `skills/job-scout/references/search-config.md` and `scoring-rubric.md` define current Pass 1/2/3 budgets and tiering — both will need v0.4 updates

**Why now (incident context).** Today's two `/scout-run` invocations (one scheduled, one interactive) proved:
1. Marketing career pages are JS-rendered SPAs — Chrome navigation succeeds but listing extraction fails reliably
2. The LinkedIn `f_C` company filter is broken — we cannot scope LinkedIn search to specific companies, so the warm-path signal is lost
3. Both runs collapsed to LinkedIn keyword search alone, missing top-connection companies entirely

ATS providers cover ~80% of the relevant employers and expose public JSON APIs that don't need rendering. v0.4 makes ATS the primary path.

**Reliability concerns to keep flagged** (from `.planning/codebase/CONCERNS.md`):
- Existing scraping logic is duplicated across boards — v0.4 should not introduce a 6th copy of the same per-source pattern; build one ATS dispatcher with provider modules
- Schema extension must go through `scripts/schema.py` to avoid drift with the tracker/CSV writers
- LinkedIn JD lazy-load is fragile; v0.4 reduces dependency on it (only A-tier ATS jobs need it for connection enrichment)

## Constraints

- **Tech stack**: Stay within Python 3.8+ stdlib + existing deps (`pandas`, `openpyxl`). New HTTP calls use `urllib.request` or add a single new dep (`httpx` or `requests`) — no new framework
- **Plugin runtime**: All work runs inside the Claude Code plugin runtime; no external services to deploy
- **Performance**: `/scout-run` wall-clock ≤ 5 minutes end-to-end (currently 10–15)
- **Reliability**: Pass 1 (ATS) must contribute ≥60% of A/B-tier candidates in the daily report — this is the milestone bar
- **Compatibility**: User data files (`master_targets.csv`, `JobScout_Tracker.xlsx`, `state.json`) must remain readable by older `/scout-run` invocations during the migration; schema additions must be additive (new optional columns, no column drops or renames in v0.4)
- **No backwards compat shim for marketing-page scraping**: that code is deleted, not flagged

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| ATS providers in v0.4: Greenhouse, Lever, Ashby, SmartRecruiters, Workday | Highest coverage of the relevant employer set; covers ~80% of top-connection companies | — Pending |
| Hybrid ATS detection (top-30 batch + lazy inline for the rest) | Balances upfront work for high-value targets against effort to detect everywhere | — Pending |
| New `/scout-detect` skill (vs. inline in `scout-setup`) | Reusable when companies are added later; cleaner separation of concerns | — Pending |
| Pass 1 first, Pass 2 dedupes against Pass 1 (vs. parallel-merge) | Simpler control flow; ATS is the canonical source so it should anchor | — Pending |
| Dedupe key: company-slug + normalized-title fuzzy match | Simple, fast, good enough for v0.4; URL-canonicalization deferred | — Pending |
| ATS-sourced jobs get +1 tier bump | Warm path + structured data is higher signal than keyword scrape | — Pending |
| Enrich-then-tier for ATS A-candidates (LinkedIn shared-connection lookup) | Restores the warm-path signal that pure ATS results lack | — Pending |
| Trust ATS on 0/error (no Chrome fallback) | Keeps the milestone reliability story honest; fragility is the thing we're removing | — Pending |
| Concurrent ATS calls with per-provider concurrency cap | Fast enough to stay under 5-minute wall-clock; polite enough to not get blocked | — Pending |
| Delete the existing marketing-page Chrome scraping path | Removing the fragile code is part of the milestone definition; flagging would let it rot | — Pending |
| Observability: source tag in report + run summary block + persisted `runs.jsonl` | Need all three to verify the ≥60% Pass 1 success criterion | — Pending |
| Schema extension: `ats_provider` + `ats_board_url` columns added to `MASTER_TARGETS_COLUMNS` | Single source of truth in `scripts/schema.py`; additive change preserves backwards compat | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-27 after initialization*

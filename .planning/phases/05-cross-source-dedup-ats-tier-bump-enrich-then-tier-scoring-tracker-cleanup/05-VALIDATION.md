---
phase: 5
slug: cross-source-dedup-ats-tier-bump-enrich-then-tier-scoring-tracker-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-29
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | none (invoke directly via venv python) |
| **Quick run command** | `~/.job-scout-venv/bin/python3 -m pytest tests/test_dedup_phase5.py tests/test_tracker_phase5.py -q` |
| **Full suite command** | `~/.job-scout-venv/bin/python3 -m pytest tests/ -q` |
| **Estimated runtime** | ~6 seconds (fixture-driven, no network) |

---

## Sampling Rate

- **After every task commit:** Run quick command (Phase 5 tests only)
- **After every plan wave:** Run full suite (`tests/`)
- **Before `/gsd-verify-work`:** Full suite green (37 from Phases 1-4 + new Phase 5 tests)
- **Max feedback latency:** ~7 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| DDP-01 | Two-key gate: BOTH loose (slug + first-3-tokens) AND tight (slug + full title) must agree at ≥95% to auto-merge | unit | `pytest tests/test_dedup_phase5.py::test_two_key_gate -x` | ❌ W0 |
| DDP-02 | Tiered confidence band: ≥95% auto-merge, 70–94% review, <70% keep both | unit | `pytest tests/test_dedup_phase5.py::test_tiered_band -x` | ❌ W0 |
| DDP-02 | dedup_decisions field appended to runs.jsonl line per D-4 (auto_merge/review_band/kept_separate counts) | unit | `pytest tests/test_dedup_phase5.py::test_dedup_decisions_logged -x` | ❌ W0 |
| DDP-03 | +1 ATS tier bump only when posted_date ≤30d ago (stale ATS does NOT bump) | unit | `pytest tests/test_dedup_phase5.py::test_ats_tier_bump_30d -x` | ❌ W0 |
| DDP-04 | LinkedIn slug derived at runtime from company_name (D-3 — no schema bump) | unit | `pytest tests/test_dedup_phase5.py::test_linkedin_slug_runtime -x` | ❌ W0 |
| DDP-04 | Enrichment runs on PRE-BUMP A-tier candidates (D-1 — base+ATS-bump → A) | unit | `pytest tests/test_dedup_phase5.py::test_enrich_pre_bump -x` | ❌ W0 |
| DDP-05 | Enrich-then-tier order: enrich BEFORE final scoring (not after) | unit | `pytest tests/test_dedup_phase5.py::test_enrich_then_tier_order -x` | ❌ W0 |
| DDP-06 | Regression-suspect: company that had OK_WITH_RESULTS ≥3/5 prior runs but OK_ZERO today is flagged | unit | `pytest tests/test_dedup_phase5.py::test_regression_suspect -x` | ❌ W0 |
| DDP-06 | regression_suspects field appended to runs.jsonl per D-2 (extends, no new file) | unit | `pytest tests/test_dedup_phase5.py::test_regression_suspects_logged -x` | ❌ W0 |
| DDP-07 | Pass-2 board-broken: Chrome scrape failures detected and flagged | unit | `pytest tests/test_dedup_phase5.py::test_pass2_board_broken -x` | ❌ W0 |
| DDP-07 | pass2_board_status field appended to runs.jsonl per D-2 | unit | `pytest tests/test_dedup_phase5.py::test_pass2_board_status_logged -x` | ❌ W0 |
| DDP-08 | Chrome MCP scoped to LinkedIn-only (no marketing-page calls in Phase 5+) | grep gate | `grep -rn "chrome-marketing\|career-page-scrape" skills/` returns 0 | n/a |
| CON-09 | Dead `pipeline_tier` Pass-1 priority + +5 bonus removed/rewritten | grep + unit | `grep -c "pipeline_tier" scripts/` after fix; pytest assertion on new behavior | ❌ W0 |
| CON-10 | LinkedIn rate-limit/backoff in enrichment — 429 responses trigger exponential backoff | unit (mock) | `pytest tests/test_dedup_phase5.py::test_linkedin_backoff -x` | ❌ W0 |
| CON-11 | LinkedIn JD lazy-load resilience — wait for content before scrape | smoke (manual) + unit on parser | `pytest tests/test_dedup_phase5.py::test_jd_resilient_parse -x` | ❌ W0 |
| CON-12 | Split `extract_job_id` → `extract_linkedin_job_id` + `extract_dedup_key` | unit | `pytest tests/test_tracker_phase5.py::test_extract_linkedin_job_id -x` + `::test_extract_dedup_key -x` | ❌ W0 |
| CON-13 | Local var rename `skipped_stale` → `flagged_stale_count`. Returned dict key stays `flagged_stale` (don't break SKILL.md Step 7) | unit | `pytest tests/test_tracker_phase5.py::test_flagged_stale_count_var -x` | ❌ W0 |
| CON-14 | Pass-2 board-broken warnings surface in report Honest notes section (related to DDP-07) | smoke | grep SKILL.md for the new prose | ❌ W0 |
| CON-15 | User-added xlsx columns survive `_write_tracker` round-trip (CRITICAL — user data preservation) | unit | `pytest tests/test_tracker_phase5.py::test_user_column_preservation -x` | ❌ W0 |
| CON-20 | (Verify exact wording from REQUIREMENTS.md — likely scoring/tracker related) | unit | `pytest tests/test_tracker_phase5.py::test_con20 -x` | ❌ W0 |
| Inherited from Phase 4 | JSON-LD routing for ats_provider="none" + career_page_url (NOT careers_url per D-4) | unit | `pytest tests/test_dedup_phase5.py::test_jsonld_routing_career_page_url -x` | ❌ W0 |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Locked Decisions (from research review 2026-04-29)

D-1: **Enrichment scope = pre-bump A-tier**. Enrich any candidate whose base + ATS-bump (if applicable) reaches A-tier, BEFORE final scoring. Restores warm-path signal for ATS listings that would be B without enrichment.

D-2: **All Phase 5 telemetry extends `runs.jsonl`**. Add 3 new keys to the existing run line: `dedup_decisions`, `regression_suspects`, `pass2_board_status`. No new files. `append_run()` gets new optional kwargs.

D-3: **LinkedIn slug derived at runtime** from company_name (lower + replace spaces with dashes + strip suffixes). No schema bump (no new master_targets column).

D-4: **`career_page_url` is the column for JSON-LD routing** (NOT `careers_url` — column doesn't exist). Phase 4's deferred VERIFICATION wording was wrong; this VALIDATION uses the correct column name.

---

## Wave 0 Requirements

- [ ] `tests/test_dedup_phase5.py` — covers DDP-01..08 + CON-10/11
- [ ] `tests/test_tracker_phase5.py` — covers CON-12, CON-13, CON-15, CON-20
- [ ] `tests/fixtures/linkedin_candidates_sample.json` — 3-listing Pass 2 fixture for cross-source dedup
- [ ] `tests/fixtures/ats_raw_sample/` — matching ATS listings for overlap scenarios (1 auto-merge pair, 1 review-band pair, 1 keep-both pair)
- [ ] `tests/fixtures/runs_jsonl_history.jsonl` — 5+ prior run lines for regression-suspect tests
- [ ] Framework already installed (pytest in venv); no new pip installs

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live LinkedIn enrichment against a real ATS A-candidate | DDP-04 | Requires Chrome MCP + real LinkedIn session | After execute-phase: run `/scout-run` against a master_targets entry with known shared connections; inspect report for warm-path block |
| Live LinkedIn rate-limit backoff | CON-10 | Requires real 429 from LinkedIn | Hard to reproduce; verify via mock-based unit test + manual probe with rapid-fire requests |
| Pass-2 board-broken warning surfaces in report Honest notes | DDP-07 / CON-14 | Requires Chrome scrape failure | Add a known-broken board to master_targets, run `/scout-run`, confirm warning appears |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers `tests/test_dedup_phase5.py` + `tests/test_tracker_phase5.py` + 3 fixture sets
- [ ] No watch-mode flags
- [ ] Feedback latency < 7s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner approves Wave 0 task structure)

**Approval:** pending

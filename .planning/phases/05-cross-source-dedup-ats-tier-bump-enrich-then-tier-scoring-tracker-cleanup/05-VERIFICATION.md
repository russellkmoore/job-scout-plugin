---
phase: 05-cross-source-dedup-ats-tier-bump-enrich-then-tier-scoring-tracker-cleanup
verified: 2026-04-28T00:00:00Z
status: passed
score: 16/16 must-haves verified
overrides_applied: 0
---

# Phase 5: Cross-source dedup + ATS tier bump + enrich-then-tier + scoring/tracker cleanup — Verification Report

**Phase Goal:** Tiered confidence band + two-key fuzzy dedup of Pass 2 against Pass 1, conditional +1 ATS tier bump (≤30d), LinkedIn shared-connection enrichment for ATS A-candidates only, ATS regression-suspect warnings in report's Honest notes section, Chrome MCP scoped to LinkedIn-only. Plus the scoring/tracker cleanup landing on the same surfaces.
**Verified:** 2026-04-28
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Same role in Pass 1 + Pass 2 produces one merged row, dedup decision in runs.jsonl | ✓ VERIFIED | `run_cross_source_dedup()` in `scripts/ats/dedupe.py` — merged list, decisions[] audit trail. `append_run()` accepts `dedup_decisions` kwarg. Test `test_two_key_gate` + `test_dedup_decisions_logged` pass. |
| 2 | Borderline dedup matches (70–94) appear in Honest notes as "possible duplicates flagged" | ✓ VERIFIED | `review_band` result key in `dedupe.py:run_cross_source_dedup`. SKILL.md Step 4.5 reads `review_band[]` and Step 6 "Dedup decisions" section surfaces them explicitly. |
| 3 | ATS listing ≤30d shows +1 tier bump; >30d gets no bump | ✓ VERIFIED | `compute_ats_tier_bump()` in `dedupe.py` lines 111–130. Test `test_ats_tier_bump_30d` passes all three cases (today=1, 31d=0, LinkedIn=0). |
| 4 | ATS A-tier candidates carry shared-connection enrichment via Chrome MCP; Chrome scoped LinkedIn-only | ✓ VERIFIED | SKILL.md Step 5 calls `is_enrichment_candidate` → Chrome navigate to `linkedin.com/company/<slug>/people/`. "There are NO career-page or marketing-page Chrome calls anywhere in the enrichment loop." (DDP-07). |
| 5 | ATS regression suspects appear in Honest notes | ✓ VERIFIED | `_find_regression_suspects()` in `runs_log.py` lines 168–224. SKILL.md Step 6 "ATS regression suspects" section calls `runs_log.py regression-suspects`. Test `test_regression_suspect` passes. |
| 6 | `grep -rn "pipeline_tier" skills/` returns zero matches | ✓ VERIFIED | Grep confirmed zero results. `scoring-rubric.md` now has "ATS warm path" row as tier elevation. `search-config.md` Pass 1 priority uses `linkedin_connection_count`. |
| 7 | LinkedIn rate-limit: 10–15s pause after every 5th navigation; JD lazy-load resilient | ✓ VERIFIED | SKILL.md Step 5 lines 355–361: "pause 10–15 seconds before the next navigation … GLOBAL across all enrichment calls." `chrome-setup.md` has multi-selector: "...more" → "Show more" → `aria-label="Expand description"` + 500-char retry. Tests `test_linkedin_backoff` + `test_jd_resilient_parse` pass. |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/ats/dedupe.py` | Two-key fuzzy dedup + tier bump + enrichment scope helper | ✓ VERIFIED | 445 lines. `run_cross_source_dedup()`, `compute_ats_tier_bump()`, `is_enrichment_candidate()`, `derive_linkedin_slug()` all present and substantive. |
| `scripts/tracker_utils.py` | split extract_job_id, rename skipped_stale, preserve user xlsx columns | ✓ VERIFIED | `extract_linkedin_job_id()` + `extract_dedup_key()` split at lines 72–117. `_write_tracker` preserves user columns via `user_extra_headers` passthrough (CON-20). |
| `scripts/ats/runs_log.py` | D-2 Optional kwargs: dedup_decisions, regression_suspects, pass2_board_status | ✓ VERIFIED | `append_run()` accepts all three Optional kwargs (lines 98–100). `_find_regression_suspects()` + `_find_pass2_board_broken()` + CLI subcommands present. |
| `skills/scout-run/SKILL.md` | Step 2.5 JSON-LD routing, Step 4.5 dedup, Step 5 enrich-then-tier, Step 6 Honest notes | ✓ VERIFIED | All four steps present with concrete Bash call patterns. |
| `skills/job-scout/references/scoring-rubric.md` | ATS warm path as tier elevation, no pipeline_tier | ✓ VERIFIED | Line 111: "ATS warm path | +1 tier | source=ats:* AND posted_date ≤ 30 days … tier elevation (B→A, C→B; A stays A capped)". |
| `skills/job-scout/references/search-config.md` | Pass 1 priority uses linkedin_connection_count, no pipeline_tier | ✓ VERIFIED | Line 51–52: "Priority order within Pass 1: Companies with 3+ named connections … Companies with linkedin_connection_count ≥ 1 AND ats_provider populated." |
| `skills/job-scout/references/chrome-setup.md` | Multi-selector resilience, 500-char retry, rate-limit cross-reference | ✓ VERIFIED | Lines 43–59: CON-12 multi-selector block present. Line 67: rate-limit cross-reference to SKILL.md Step 5. |
| `templates/config.json` | `dedup.thresholds.auto_merge: 95` and `review_band_min: 70` | ✓ VERIFIED | Confirmed via `python3 -c "import json; ..."` — both thresholds present. |
| `tests/test_dedup_phase5.py` | 14 tests covering DDP-01..08, CON-10/11 | ✓ VERIFIED | 14 tests present, all pass. |
| `tests/test_tracker_phase5.py` | 9 tests covering CON-13/14/20 | ✓ VERIFIED | 9 tests present, all pass. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| SKILL.md Step 2.5 | `ats_provider == "none" AND career_page_url` | `career_page_url\|jsonld` entries in targets_csv | ✓ WIRED | Lines 168–191: D-4 column guard + JSON-LD routing instructions explicit. |
| SKILL.md Step 4.5 | `scripts/ats/dedupe.py cross-source` | Bash call with ats_raw/, linkedin_candidates.json, dedup_result.json | ✓ WIRED | Lines 292–297: concrete Bash call present. |
| SKILL.md Step 5 | `scripts/ats/dedupe.is_enrichment_candidate` | inline Python call with listing, base_score, today | ✓ WIRED | Line 329: "Use `scripts/ats/dedupe.is_enrichment_candidate(listing, base_score, today)`" |
| SKILL.md Step 5 | `scripts/ats/dedupe.derive_linkedin_slug` | inline Python call per company | ✓ WIRED | Lines 339–340: "Use `scripts/ats/dedupe.derive_linkedin_slug(company_name)`" |
| SKILL.md Step 6 | `scripts/ats/runs_log.py regression-suspects` | Bash call with runs.jsonl | ✓ WIRED | Lines 445–449: concrete Bash call present. |
| SKILL.md Step 6 | `scripts/ats/runs_log.py pass2-board-broken` | Bash call with runs.jsonl | ✓ WIRED | Lines 468–470: concrete Bash call present. |
| `runs_log.append_run` | D-2 Optional kwargs | `dedup_decisions`, `regression_suspects`, `pass2_board_status` | ✓ WIRED | All three kwargs accepted in function signature and conditionally emitted to JSONL (lines 98–157). Backward compatible: preview.py and detect.py callers unchanged. |
| `tracker_utils._write_tracker` | user_extra_headers passthrough | `if col > len(HEADERS): continue` | ✓ WIRED | Lines 366–368: user headers re-emitted in row 1. Lines 394–396: user column values written through without scout formatting. Break replaced with continue. |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `dedupe.run_cross_source_dedup` | ats_listings, linkedin_listings | ATS raw dir + linkedin_candidates.json | Yes — real file reads via _cmd_cross_source | ✓ FLOWING |
| `runs_log.append_run` | dedup_decisions, regression_suspects, pass2_board_status | Passed from caller (SKILL orchestration) | Yes — Optional kwargs emitted when non-empty | ✓ FLOWING |
| `tracker_utils._write_tracker` | user_extra_headers | load_tracker 4-tuple return | Yes — read from existing xlsx row 1 | ✓ FLOWING |

---

### Behavioral Spot-Checks

Step 7b: SKIPPED for SKILL.md (LLM-orchestrated prompt, no runnable entry point). Python module spot-checks used test suite instead.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 60/60 tests pass (incl. Phase 5) | `pytest tests/test_dedup_phase5.py tests/test_tracker_phase5.py -v` | 23/23 passed in 0.18s | ✓ PASS |
| Full suite regression | `pytest tests/ -v` | 60/60 passed in 0.53s | ✓ PASS |
| dedupe.py importable | implicit via pytest | All 14 dedup tests pass | ✓ PASS |
| runs_log.py CLI subcommands | implicit via test_regression_suspects_logged + test_pass2_board_status_logged | Both pass | ✓ PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| DDP-01 | 05-02-PLAN | per-company-slug fuzzy dedup of Pass 2 vs Pass 1 | ✓ SATISFIED | `run_cross_source_dedup` groups ATS by slug, matches per slug |
| DDP-02 | 05-02-PLAN | Tiered confidence band: ≥95 auto-merge, 70–94 review, <70 keep-both | ✓ SATISFIED | Lines 259–307 in dedupe.py; config thresholds confirmed |
| DDP-03 | 05-02-PLAN | Two-key gate: BOTH loose AND tight must pass auto-merge | ✓ SATISFIED | Line 259: `if loose_score >= auto_merge and tight_score >= auto_merge` |
| DDP-04 | 05-02-PLAN | dedup decisions appended to runs.jsonl under `dedup_decisions` | ✓ SATISFIED | `append_run(dedup_decisions=...)` kwarg; test_dedup_decisions_logged passes |
| DDP-05 | 05-02-PLAN | scoring-rubric.md updated with +1 tier bump for ATS ≤30d | ✓ SATISFIED | scoring-rubric.md line 111: "ATS warm path | +1 tier | source=ats:* AND posted_date ≤ 30 days" |
| DDP-06 | 05-05-PLAN | SKILL.md Step 5 enrich-then-tier for ATS A-tier via Chrome MCP | ✓ SATISFIED | SKILL.md Step 5 (a): is_enrichment_candidate → derive_linkedin_slug → Chrome navigate |
| DDP-07 | 05-05-PLAN | Chrome MCP limited to LinkedIn; no career-page scraping in enrichment | ✓ SATISFIED | SKILL.md Step 5: "There are NO career-page or marketing-page Chrome calls anywhere in the enrichment loop." |
| DDP-08 | 05-04-PLAN | ATS regression suspects in Honest notes | ✓ SATISFIED | SKILL.md Step 6 "ATS regression suspects" section + `runs_log.py regression-suspects` CLI |
| CON-09 | 05-05-PLAN | Dead `pipeline_tier` Pass 1 priority in search-config.md rewritten | ✓ SATISFIED | Zero grep results for `pipeline_tier` in skills/. search-config.md uses `linkedin_connection_count` thresholds. |
| CON-10 | 05-05-PLAN | Dead `pipeline_tier` +5 bonus in scoring-rubric.md rewritten | ✓ SATISFIED | scoring-rubric.md "ATS warm path" row replaces former pipeline_tier row |
| CON-11 | 05-05-PLAN | LinkedIn rate-limit 10–15s pause in SKILL.md Step 5 | ✓ SATISFIED | SKILL.md Step 5 lines 355–361; test_linkedin_backoff passes |
| CON-12 | 05-05-PLAN | JD lazy-load multi-selector + 500-char retry in chrome-setup.md | ✓ SATISFIED | chrome-setup.md lines 43–59; test_jd_resilient_parse passes |
| CON-13 | 05-03-PLAN | split extract_job_id → extract_linkedin_job_id + extract_dedup_key | ✓ SATISFIED | Both functions present in tracker_utils.py lines 72–117; all 4 callers migrated; extract_job_id deprecated (Phase 6 deletion) |
| CON-14 | 05-03-PLAN | Rename local var `skipped_stale` → `flagged_stale_count`; dict key stays `flagged_stale` | ✓ SATISFIED | tracker_utils.py line 240: `flagged_stale_count = 0  # CON-14: local var (dict key stays "flagged_stale" per Pitfall 6)`. Line 310: `"flagged_stale": flagged_stale_count`. test_flagged_stale_count_var passes. |
| CON-15 | 05-04-PLAN | Pass-2 board-broken warnings in Honest notes | ✓ SATISFIED | `_find_pass2_board_broken()` + `pass2-board-broken` CLI in runs_log.py. SKILL.md Step 3 captures pass2_board_status; Step 6 surfaces board-broken warnings. test_pass2_board_broken passes. |
| CON-20 | 05-03-PLAN | _write_tracker preserves user-added xlsx columns on append | ✓ SATISFIED | `_write_tracker(user_extra_headers=...)` passthrough in lines 345–413. The old `break` replaced with `continue`. load_tracker returns 4-tuple. Both round-trip tests pass. |

---

### Locked Decisions Verification

| Decision | Requirement | Status | Evidence |
|----------|-------------|--------|---------|
| D-1: Enrichment scope = pre-bump A-tier | `is_enrichment_candidate()` exists; SKILL.md Step 5 enriches BEFORE tier assignment | ✓ VERIFIED | dedupe.py lines 133–167; SKILL.md Step 5 order: (a) enrich → (b) score with enriched data → (c) assign final tier |
| D-2: All telemetry extends runs.jsonl (no new files) | `append_run()` accepts Optional kwargs; preview.py + detect.py still work | ✓ VERIFIED | runs_log.py lines 98–100 Optional params. preview.py calls append_run without D-2 kwargs (backward compat preserved). |
| D-3: LinkedIn slug runtime derivation | `derive_linkedin_slug()` exists; no new master_targets column | ✓ VERIFIED | dedupe.py lines 85–108. SKILL.md Step 5 line 340: "Use `scripts/ats/dedupe.derive_linkedin_slug(company_name)`". test_linkedin_slug_runtime passes all 4 cases. |
| D-4: career_page_url (not careers_url) | SKILL.md Step 2.5 uses `career_page_url`; `grep -rn "careers_url" skills/` returns zero matches | ✓ VERIFIED | Zero grep results for `careers_url` in skills/. SKILL.md lines 173–191 consistently use `career_page_url`. schema.py MASTER_TARGETS_COLUMNS contains `career_page_url` not `careers_url`. Note: jsonld.py uses `careers_url` only as an internal parameter/docstring name, not a CSV column accessor. |

---

### Pitfall Verification

| Pitfall | Check | Status |
|---------|-------|--------|
| P1: Step 5 enrichment BEFORE final tier | SKILL.md Step 5 order: enrich (a) → score (b) → assign tier (c) | ✓ PREVENTED |
| P2: `_write_tracker` no longer drops user columns (`break` → write-through) | tracker_utils.py line 394: `if col > len(HEADERS): continue` (not break) | ✓ PREVENTED |
| P3: `_normalize_title` imported from ats.normalize, never copy-pasted | dedupe.py line 35: `from ats.normalize import _normalize_title  # Pitfall 3 — IMPORT, never copy` | ✓ PREVENTED |
| P4: zero `careers_url` in skills/ | `grep -rn "careers_url" skills/` returns 0 matches | ✓ PREVENTED |
| P5: regression-suspect uses `lines[-(lookback+1):-1]` slicing | runs_log.py line 194: `prior = lines[-(lookback + 1):-1] if len(lines) > lookback else lines[:-1]` | ✓ PREVENTED |
| P6: `result["flagged_stale"]` dict key UNCHANGED (not `flagged_stale_count`) | tracker_utils.py line 310: `"flagged_stale": flagged_stale_count` | ✓ PREVENTED |

---

### Anti-Patterns Found

No blockers. No stub patterns found in Phase 5 modified files.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `skills/scout-run/SKILL.md` | — | `[ATS-PREVIEW]` tag + prose note "Phase 5 will hoist into Pass 1" in Step 2.5 | ℹ️ Info | Phase 2-4 migration banner. Intentional — Phase 6 removes it. Not a stub. |
| `scripts/tracker_utils.py` | 113 | `extract_job_id` DEPRECATED back-compat wrapper | ℹ️ Info | Phase 6 removal scheduled. Back-compat wrapper is correct pattern for this migration. |

---

### Human Verification Required

None. All automated checks pass with high confidence.

---

### Gaps Summary

None. All 16 requirements (DDP-01..08, CON-09..15, CON-20), all 4 locked decisions, all 6 pitfalls, and all 60 tests are verified against the actual codebase.

The Phase 5 cherry-pick recovery from worktree base mismatch (Plan 05-05 commits f87918a, 5089cd9, 8e4e0a1) produced clean code with no observable artifacts from the conflict resolution.

---

_Verified: 2026-04-28_
_Verifier: Claude (gsd-verifier)_

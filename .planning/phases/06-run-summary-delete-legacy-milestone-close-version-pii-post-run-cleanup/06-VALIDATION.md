---
phase: 6
slug: run-summary-delete-legacy-milestone-close-version-pii-post-run-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-29
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Phase 6 is the milestone closer — most work is grep gates + version bumps + small unit tests for the milestone bar calc.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | none |
| **Quick run command** | `~/.job-scout-venv/bin/python3 -m pytest tests/test_runs_log_phase6.py -x -q` |
| **Full suite command** | `~/.job-scout-venv/bin/python3 -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds (no network) |

---

## Sampling Rate

- **After every task commit:** Quick run (Phase 6 tests only)
- **After every plan wave:** Full suite (`tests/`)
- **Before `/gsd-verify-work`:** Full suite green (60 from Phases 1-5 + new Phase 6 tests) + phase-wide grep gate
- **Max feedback latency:** ~6 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| OUT-01 | Run summary block at top of report.md (per-pass counts, wall-clock, regression-suspects) | smoke (grep) | grep top-of-file headers in template/sample report | n/a |
| OUT-02 | Run summary printed to stdout (machine-readable JSON mirror) | smoke | grep SKILL.md Step 7 for the JSON-print invocation | n/a |
| OUT-03 | Marketing-page Chrome scraping path DELETED (zero matches in skills/ + scripts/, with exclusions) | grep gate | `grep -rni "marketing-page\|marketing page" skills/ scripts/ --exclude-dir=fixtures` returns 0 | n/a |
| OUT-04 | chrome-setup.md trimmed to LinkedIn-only | grep gate | `grep -c "marketing\|career.*page.*scrape" skills/job-scout/references/chrome-setup.md` returns 0 | n/a |
| OUT-05 | Version bump: plugin.json + 3 SKILL.md frontmatter to 0.4.0 in lockstep | grep gate | exactly 4 `0.4.0` matches across plugin.json + SKILL.md frontmatter | n/a |
| OUT-06 | README update reflects v0.4 capabilities | smoke | grep README for "5 ATS providers", "JSON-LD", "dedup", "enrich-then-tier" markers | n/a |
| OUT-07 (D-1) | `compute_milestone_bar` returns pass1_share = ab_ats / (ab_ats + ab_linkedin) from runs.jsonl | unit | `pytest tests/test_runs_log_phase6.py::test_milestone_bar_pass1_share -x` | ❌ W0 |
| OUT-07 (D-2) | `compute_milestone_bar` wall_clock_avg = mean(wall_clock_seconds) across last 5 runs (ATS-fetch only) | unit | `pytest tests/test_runs_log_phase6.py::test_milestone_bar_wall_clock -x` | ❌ W0 |
| OUT-07 | `milestone-bar` CLI subcommand exits 0, prints JSON | unit | `pytest tests/test_runs_log_phase6.py::test_milestone_bar_cli -x` | ❌ W0 |
| OUT-07 | `milestone-bar` with <5 runs uses available runs (not error) | unit | `pytest tests/test_runs_log_phase6.py::test_milestone_bar_short_history -x` | ❌ W0 |
| OUT-07 | `milestone-bar` with missing `ab_tier_counts` field returns pass1_share_pct: null | unit | `pytest tests/test_runs_log_phase6.py::test_milestone_bar_missing_field -x` | ❌ W0 |
| OUT-07 | `source=` tag present on every report listing | grep | `grep -c "Source: " sample_report.md` matches listing count | n/a |
| CON-16 | inline column list in skills/job-scout/SKILL.md:38 deleted (single source of truth — schema.py owns columns) | grep | `grep -c "company_name.*linkedin_connection_count.*ats_provider" skills/job-scout/SKILL.md` returns 0 | n/a |
| CON-17 | PII handling note + .gitignore template entry to /scout-setup | grep | grep scout-setup/SKILL.md for "PII" + "gitignore" markers | n/a |
| CON-18 | Post-write validation check at end of /scout-run Step 6 | grep | grep scout-run/SKILL.md for `validate_data.py post-write` invocation | n/a |
| CON-19 | (Verify exact wording from REQUIREMENTS.md) | TBD | TBD | n/a |
| CON-21 | (Verify exact wording from REQUIREMENTS.md) | TBD | TBD | n/a |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Locked Decisions (from research review 2026-04-29)

D-1: **Tier-aware Pass-1 share.** runs.jsonl gets new `ab_tier_counts: {"ats": N, "linkedin": M}` field written at end of /scout-run Step 5 after tier assignment. `compute_milestone_bar` reads this; pass1_share = `sum(ats over last 5 runs) / sum(ats + linkedin over last 5 runs)`. Missing field on older runs → field treated as `{"ats": 0, "linkedin": 0}` for that run; if all 5 runs missing → return `pass1_share_pct: null` (don't crash).

D-2: **ATS-fetch-only wall-clock.** `compute_milestone_bar` wall_clock_avg = mean of existing `wall_clock_seconds` field (dispatcher fetch_all duration only). NOT total /scout-run wall-clock. README + chrome-setup.md document this scope explicitly so users don't expect total-time measurement.

---

## Wave 0 Requirements

- [ ] `tests/test_runs_log_phase6.py` — 5 unit tests covering `compute_milestone_bar` + CLI subcommand + edge cases (short history, missing field, malformed JSON)
- [ ] No new fixture files (existing `runs_jsonl_history.jsonl` from Phase 5 covers most scenarios; tests use synthetic inline JSONL strings via `tmp_path`)

---

## Phase-Wide Grep Gate (Plan 06-N final task)

A single bash gate that runs all the OUT-03/04/05 + CON-16 grep checks together. If any fail, phase verification fails.

```bash
# OUT-03: marketing-page Chrome scraping deleted
grep -rni "marketing-page\|marketing page" skills/ scripts/ --exclude-dir=fixtures --exclude-dir=__pycache__ | wc -l   # must equal 0

# OUT-04: chrome-setup.md scoped to LinkedIn-only
grep -c "marketing\|career.*page.*scrape" skills/job-scout/references/chrome-setup.md   # must equal 0

# OUT-05: version sprawl normalized
grep -h "^version:" skills/*/SKILL.md | grep -c "0.4.0"   # must equal 3 (3 SKILL.md files)
grep '"version"' .claude-plugin/plugin.json | grep -c "0.4.0"   # must equal 1

# CON-16: inline column list deleted
grep -c "company_name.*linkedin_connection_count.*ats_provider" skills/job-scout/SKILL.md   # must equal 0
```

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `/scout-run` end-to-end smoke against real master_targets.csv | OUT-01..02, OUT-07 | Requires real network + real Chrome + real LinkedIn session | After execute-phase: `/scout-run` once, inspect `report.md` for run summary block, inspect `runs.jsonl` for `ab_tier_counts` field, run `runs_log.py milestone-bar` to confirm 4-criterion JSON output |
| 5-run rolling Pass-1 share calculation against real history | OUT-07 SC-1 | Requires 5+ real runs accumulated over days | After 5 daily `/scout-run` invocations, `runs_log.py milestone-bar` should report `pass1_share_pct` with real values |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Phase-wide grep gate passes
- [ ] No watch-mode flags
- [ ] Feedback latency < 6s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner approves)

**Approval:** pending

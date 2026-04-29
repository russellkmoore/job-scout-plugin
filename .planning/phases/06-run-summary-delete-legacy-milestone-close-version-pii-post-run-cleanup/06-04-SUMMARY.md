---
phase: 06
plan: 04
subsystem: skills/scout-run + scripts/ats/preview.py
tags: [ats-first, skill-integration, version-bump, observability, milestone-bar]
dependency_graph:
  requires: [06-02, 06-03]
  provides: [scout-run/SKILL.md v0.4.0, Run Summary block, Step 7.5 validation, ab_tier_counts write, [ATS-PREVIEW] brand eliminated]
  affects: [skills/scout-run/SKILL.md, scripts/ats/preview.py, scripts/ats/_verify_06_04_task1.sh, scripts/ats/_verify_06_04_task2.sh]
tech_stack:
  added: []
  patterns: [SKILL.md surgical edit, non-blocking validation, stats.json passthrough, milestone-bar CLI invocation]
key_files:
  created: [scripts/ats/_verify_06_04_task1.sh, scripts/ats/_verify_06_04_task2.sh]
  modified: [skills/scout-run/SKILL.md, scripts/ats/preview.py]
decisions:
  - D-1 implemented: ab_tier_counts write in Step 5(d) passes ats/linkedin A/B counts to runs_log.append_run; C-tier excluded per ROADMAP SC-5
  - D-2 documented: Run Summary block explicitly labels wall-clock as "ATS-fetch only, NOT total /scout-run wall-clock"
metrics:
  duration: ~30 minutes
  completed: "2026-04-29T21:10:23Z"
  tasks_completed: 3
  files_modified: 4
---

# Phase 6 Plan 04: scout-run/SKILL.md Flow Integration + Version Bump + preview.py Docstring Cleanup

**One-liner:** Full v0.4.0 integration of ATS-first flow into scout-run/SKILL.md — Step 2 marketing-page deletion, [ATS-PREVIEW] brand elimination, ab_tier_counts wiring, Run Summary block, Step 7.5 post-write validation, Step 9 stdout mirror — plus preview.py docstring brand cleanup.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Step 2 deletion + Step 2.5 banner cleanup + frontmatter v0.4.0 | d1db7e8 | skills/scout-run/SKILL.md, scripts/ats/_verify_06_04_task1.sh |
| 2 | Step 5 ab_tier_counts + Step 6 Run Summary + Step 7.5 validation + Step 9 stdout mirror | 8311fee | skills/scout-run/SKILL.md, scripts/ats/_verify_06_04_task2.sh |
| 3 | scripts/ats/preview.py docstring brand cleanup | 4e31f5c | scripts/ats/preview.py |

## Surgical Edits — scout-run/SKILL.md

### Task 1 Edits

1. **Frontmatter version bump (CON-16):** `version: 0.3.3` → `version: 0.4.0`. Completes 4-of-4 SKILL.md lockstep (scout-detect was already 0.4.0; scout-setup and job-scout bumped in Plan 06-03).

2. **Frontmatter description rewrite (CON-16):** Replaced `"broad sourcing across LinkedIn, career pages, and other boards"` with ATS-first description listing all 5 providers + JSON-LD fallback + specialized boards. Trigger phrases preserved verbatim.

3. **Step 2 deletion (P1, P3, OUT-04):** Removed items 1 (Career page direct read) and 2 (ATS board Chrome navigation). Item 3 (LinkedIn keyword search) preserved verbatim — including `f_C=` rationale, `f_TPR=r604800` URL pattern, and "verified 2026-04-27 run" empirical evidence. Replaced deleted items with redirect prose: "ATS sourcing runs in **Step 2.5** (multi-provider, ONE process per run)."

4. **Step 2.5 heading (P2):** `## Step 2.5: [ATS-PREVIEW] Pass 1 (Greenhouse only) — additive` → `## Step 2.5: Pass 1 (ATS) — all providers`

5. **Step 2.5 "What this is" block (P2):** Replaced 3-paragraph Phase 2 migration explanation (with "Phase 5 will replace the old flow") with a single concise statement: ATS-first sourcing, all providers, one process, flows into unified scoring + dedup.

6. **Step 2.5 stdout capture line (P2):** `"render the [ATS-PREVIEW] block in Step 6"` → `"populate the Run Summary block in Step 6"`

7. **Step 2.5 render block (P2):** Replaced the separate `### [ATS-PREVIEW] ATS listings` render block with "Pass listings into the unified candidate set" prose — ATS listings render in standard A/B/C tier blocks.

8. **Step 2b lazy detection references (P2):** Fixed 4 occurrences in Step 2b and failure modes — `[ATS-PREVIEW] (Step 2.5 below)` → `Step 2.5 (ATS Pass 1)` patterns; `skips Steps 3/4/5/6 of the [ATS-PREVIEW] block` → `skips the remaining sub-steps of Step 2.5`.

9. **Step 2.5 failure modes (P2):** Fixed 2 remaining occurrences: `does not contribute to [ATS-PREVIEW]` → `does not contribute to Pass 1`; `skips Steps 3/4/5/6 of the [ATS-PREVIEW] block` → `skips the remaining sub-steps of Step 2.5`.

### Task 2 Insertions

10. **Step 5 (d) ab_tier_counts write (D-1, P4):** New sub-step appended after (c) "Assign final tier". Instructs SKILL to count A/B-tier listings by source after final tier assignment, build `{"ats": N, "linkedin": M, "total_ab": N+M}`, pass to `runs_log.append_run(..., ab_tier_counts=...)`. Explicit Pitfall 6 callout (missing write → `pass1_share_pct: null`). C-tier excluded per ROADMAP SC-5. Source classification rules enumerated.

11. **Step 6 Run Summary block (OUT-01, OUT-02):** New `### Run Summary block (top of report.md — OUT-02)` sub-section inserted before `### Header`. Invokes `runs_log.py milestone-bar --lookback 5`; defines Markdown template with 7 fields; documents source of each field; notes ATS-fetch-only wall-clock (D-2); all 6 providers (greenhouse, lever, ashby, smartrecruiters, workday, jsonld) in per-provider line.

12. **Step 7.5 post-write validation (CON-21, P7):** New top-level `## Step 7.5` section between Step 7 and Step 8. Three non-blocking checks: (1) report exists and is non-empty via `test -s`; (2) runs.jsonl last-line timestamp contains TODAY; (3) A-tier count using `new_rows.json` `tier` field — NOT `grep -c "^### "` (Pitfall 7 prevention). Each failure prints `WARNING: post-run validation failed: <reason>`. Final summary line: `post-run validation: <N>/3 checks passed`.

13. **Step 9 stdout mirror (OUT-03):** New `### Stdout summary mirror (OUT-03)` sub-section appended before `## On-demand`. Invokes `runs_log.py milestone-bar --lookback 5`; prints JSON output + human-readable Run Summary for cron/launchd log capture.

## Docstring Edits — scripts/ats/preview.py

| Location | Before | After |
|----------|--------|-------|
| Module docstring line 2 | `Phase 2 [ATS-PREVIEW] driver` | `ATS dispatcher driver` |
| Module docstring closing 3 lines | Phase-5-future-tense migration note | `Per-block append is the v0.4 contract; rotation/aggregation is OOS for v0.4 per project convention.` |
| `run_preview` docstring opener | `Phase 4 [ATS-PREVIEW] cycle` | `ATS Pass 1 cycle` |
| `run_preview` Returns doc | `render the [ATS-PREVIEW] block in Step 6` | `populate the Run Summary block in Step 6` |
| `--help` text | `[ATS-PREVIEW] cycle for /scout-run Step 2.5` | `ATS Pass 1 cycle for /scout-run Step 2.5` |

DSP-03 architectural commentary preserved verbatim (lines 6–16: ONE shared httpx.Client rationale, three-call problem, three-Client violation, Solution statement).

## Final State

| Check | Result |
|-------|--------|
| `grep -c '[ATS-PREVIEW]' skills/scout-run/SKILL.md` | 0 |
| `grep -c '[ATS-PREVIEW]' scripts/ats/preview.py` | 0 |
| `grep -c '^version: 0.4.0' skills/scout-run/SKILL.md` | 1 |
| `grep -h '^version:' skills/*/SKILL.md \| grep -c '0.4.0'` | 4 (all 4 SKILL.md in lockstep) |
| `grep -c 'ab_tier_counts' skills/scout-run/SKILL.md` | 3 |
| `grep -c 'ATS-fetch only' skills/scout-run/SKILL.md` | 1 |
| `grep -c 'milestone-bar' skills/scout-run/SKILL.md` | 7 |
| `grep -c '## Step 7.5' skills/scout-run/SKILL.md` | 1 |
| `grep -c "tier.*==.*'A'" skills/scout-run/SKILL.md` | 1 |
| `~/.job-scout-venv/bin/python3 -m pytest tests/ -q` | 65 passed |

## Preserved Content (confirmed verbatim)

- Step 2 item 3: LinkedIn keyword search URL (`f_C=` rationale, `f_TPR=r604800`, `f_WT=2`, "verified 2026-04-27 run")
- Step 2b: lazy inline detection flow, all failure modes
- Step 2.5: JSON-LD routing prose (D-4 locked, Pitfall 4 column-name guard, Phase 5 implementation note)
- Step 2.5: DSP-03 architectural invariant (ONE process per /scout-run)
- Step 2.5: all 5-provider slug derivation rules
- Step 4.5: cross-source dedup section (untouched)
- Step 5 (a)-(c): enrichment + scoring + tier assignment blocks (untouched; (d) appended)
- Step 6: all existing sub-sections (Header, A-tier, B-tier, C-tier, Stale, Companies checked, Honest notes, ATS regression suspects, Pass-2 board-broken warnings, Dedup decisions, Generate-on-demand packets)
- Step 9: existing chat summary prose (Stdout mirror appended, not replaced)
- preview.py: all function signatures and bodies (docstring-only changes)
- preview.py: DSP-03 contract commentary (lines 6–16)

## Deviations from Plan

### One minor scope note (not a deviation)

**[ATS-PREVIEW] occurrence in _verify_06_04_task1.sh line 34:** The phase-wide grep gate in Plan 06-05 will find 1 occurrence in `scripts/ats/_verify_06_04_task1.sh` — this is the grep pattern string `"[ATS-PREVIEW] == 0"` used as a check description in the verify script itself. It is NOT a content occurrence in a skill or production module. The 06-05 grep gate should either exclude `_verify_*.sh` files or this script should be deleted before the gate runs. Logged here so Plan 06-05 is aware.

None of the 7 planned edits required structural changes beyond the specified scope.

## Known Stubs

None. All added prose instructs the LLM on how to compute values from data already in scope at runtime. No hardcoded empty values or placeholder text that blocks plan goals.

## Threat Flags

No new network endpoints, auth paths, or file write paths introduced. Step 7.5 validation is read-only. Stdout mirror prints only summary counts and metadata — no PII, no resume_path, no connection_names (confirmed per T-06-09).

## Self-Check: PASSED

| Item | Status |
|------|--------|
| skills/scout-run/SKILL.md | FOUND |
| scripts/ats/preview.py | FOUND |
| scripts/ats/_verify_06_04_task1.sh | FOUND |
| scripts/ats/_verify_06_04_task2.sh | FOUND |
| 06-04-SUMMARY.md | FOUND |
| Commit d1db7e8 (Task 1) | FOUND |
| Commit 8311fee (Task 2) | FOUND |
| Commit 4e31f5c (Task 3) | FOUND |
| [ATS-PREVIEW] in scout-run/SKILL.md | 0 |
| [ATS-PREVIEW] in preview.py | 0 |
| All 4 SKILL.md at v0.4.0 | 4/4 |
| Test suite | 65 passed |

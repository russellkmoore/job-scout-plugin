---
phase: 02-provider-protocol-greenhouse-dispatcher-observability
plan: 03
subsystem: ats
tags: [preview-driver, scout-run-wiring, ats-preview, single-fetch_all, stash-replay-protocol, runs-jsonl-append]

# Dependency graph
requires:
  - phase: 02-provider-protocol-greenhouse-dispatcher-observability
    provides: dispatcher.fetch_all + aggregate_outcomes + FetchOutcome (Plan 02-01); runs_log.append_run + RunOutcome (Plan 02-01); PROVIDERS["greenhouse"] registered (Plan 02-02); httpx 0.28.1 installed in ~/.job-scout-venv
provides:
  - "scripts/ats/preview.py — thin driver script: ONE process invocation per /scout-run; exactly ONE call to fetch_all; persists raw payloads from each OK_WITH_RESULTS outcome; appends ONE runs.jsonl line; prints JSON summary to stdout"
  - "skills/scout-run/SKILL.md Step 2.5 — new [ATS-PREVIEW] block placed AFTER existing Step 2 and BEFORE Step 3; invokes preview.py with EXACTLY ONE Bash call; additive (existing 3-pass flow unchanged)"
  - "Stash-replay protocol re-validated for the second time on this file (Plan 01-03 was the first; commit 2e84994). Same 7-step protocol; same end state: my edit in HEAD, user's pending edits restored on top, byte-identical to session-start snapshot."
affects:
  - "Phase 3 — /scout-detect populates `ats_provider=\"greenhouse\"` for top-30 companies in master_targets.csv. AT THAT POINT the [ATS-PREVIEW] block actually exercises real network fetches against real master_targets entries (currently the slug list is empty → empty-roundtrip path)."
  - "Phase 5 — replaces the old 3-pass flow with the [ATS-PREVIEW] code path hoisted into Pass 1 anchor + applies the +1 ATS tier bump (per locked decision)."
  - "Phase 5 regression-suspect detection — reads runs.jsonl per-(company, provider) hit counts. preview.py's per-run append starts producing data NOW even with 0-outcome empty-slug runs (the daily heartbeat)."

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-driver-per-SKILL pattern — when DSP-03 (single shared httpx.Client) must be preserved across what would otherwise be multiple SKILL Bash steps, collapse all responsibilities into ONE Python script that the SKILL invokes ONCE. Verified by `grep -c 'fetch_all(' SKILL.md` == 0."
    - "Stash-replay protocol for editing files with pending uncommitted user edits — snapshot to /tmp → reset to HEAD → apply edit → commit on clean base → restore snapshot to working tree → re-apply edit on top → cleanup /tmp. Anchor matching (a heading line that's identical in HEAD and snapshot) is what makes the re-apply step work cleanly."
    - "Empty-target safety — preview.py treats empty `<slugs_csv>` as a valid heartbeat input: appends a runs.jsonl line with 0 outcomes (so Phase 5's regression-suspect detection has a daily lat/long fix even before /scout-detect populates real slugs)."

key-files:
  created:
    - "scripts/ats/preview.py — 221 lines; sibling-bootstrap (2-level); imports fetch_all + aggregate_outcomes from ats.dispatcher and append_run + RunOutcome from ats.runs_log; defines run_preview(data_dir, today, slugs, provider='greenhouse') -> dict; CLI dispatch with --help / --version / positional args (data_dir, today, slugs_csv); exits 0 on success, 2 on missing config.json, 1 on bad args"
  modified:
    - "skills/scout-run/SKILL.md — +50 lines; new ## Step 2.5: [ATS-PREVIEW] Pass 1 (Greenhouse only) — additive section between existing Step 2 and Step 3; documents the slug-derivation + ONE Bash call to preview.py + report-rendering pattern; references preview.py + runs_log.append_run + ats_raw paths; user's 2 pending uncommitted hunks (frontmatter version 0.3.3 + Step 2 LinkedIn URL pattern with f_C-disabled rationale) preserved verbatim"

key-decisions:
  - "DSP-10 ADDITIVE wire-in (locked) — Step 2.5 sits between Step 2 and Step 3, does not modify the existing Step 1/2/3/4/5/6/7/8/9/Fallback flow. Phase 5 will replace the old flow; until then both produce output. The [ATS-PREVIEW] tag marks new listings as Phase 2 plumbing (not scored, not tier-assigned)."
  - "DSP-03 PRESERVED AT THE SKILL BOUNDARY — `grep -c 'fetch_all(' skills/scout-run/SKILL.md` is 0 in HEAD (no inline heredoc fetch_all calls). The single-Client invariant is enforced in preview.py via fetch_all's own `with httpx.Client(...) as client:` block; preview.py contains exactly ONE paren-form `fetch_all(` call (the actual invocation at preview.py:130)."
  - "preview.py owns ALL three responsibilities — invoke dispatcher (fetch_all), persist raw payloads (json.dump per OK_WITH_RESULTS outcome), append runs.jsonl (append_run) — from the SAME outcomes list. ONE process → ONE httpx.Client → ONE wall_clock measurement → ONE runs.jsonl append. No cross-process state leakage."
  - "Empty-slugs path is intentional + tested — preview.py with `<slugs_csv>=\"\"` exits 0 with a printed JSON summary (`outcome_count: 0`) and appends ONE runs.jsonl heartbeat line. SKILL.md instructs the prompt to invoke preview.py even when no Greenhouse companies are in master_targets.csv (the typical Phase 2 state until Phase 3 ships /scout-detect)."
  - "Stash-replay protocol matches Plan 01-03 verbatim — same 7-step sequence, same /tmp file naming convention (-DSP10 instead of -01-03 suffix), same anchor-heading-based re-apply pattern. Final-state diff confirmed byte-identical to pre-Task-2 snapshot."
  - "preview.py docstring uses `fetch_all` (no paren) where it would otherwise have exceeded the verify gate's `grep -c 'fetch_all(' <= 2` threshold. Documentation references read clearly as prose; the only `fetch_all(` paren forms in the file are: (1) the import line `from ats.dispatcher import fetch_all, aggregate_outcomes` does NOT contain a paren; (2) the actual call at line 130 — total = 1."

patterns-established:
  - "When a future SKILL needs to invoke a Python module that opens external resources (sockets, DB connections, file handles): collapse the multi-step responsibilities into a single driver script and invoke ONCE from the SKILL. The grep-based invariant check (`grep -c 'forbidden_call(' skills/...`) is the load-bearing gate for verifying single-call shape at the SKILL boundary."
  - "Stash-replay protocol is now the established pattern for editing skills/scout-run/SKILL.md when the file has pending uncommitted user edits. Two successful applications: Plan 01-03 (commit 2e84994) and Plan 02-03 (commit f562cca)."

requirements-completed: [DSP-10]

# Metrics
duration: ~10min
completed: 2026-04-29
---

# Phase 2 Plan 03: [ATS-PREVIEW] Wire-in to /scout-run Summary

**Plan 02-01's dispatcher + Plan 02-02's Greenhouse provider are now wired into /scout-run as a NEW Step 2.5 — additively, alongside the existing 3-pass flow — via a single thin driver script (`scripts/ats/preview.py`) that the SKILL invokes ONCE per run. DSP-03 (single shared httpx.Client) preserved at the SKILL boundary by `grep -c 'fetch_all(' skills/scout-run/SKILL.md == 0`. The user's 2 pending uncommitted hunks (frontmatter version 0.3.3 + Step 2 LinkedIn URL pattern with f_C-disabled rationale) preserved byte-identical via the same stash-replay protocol Plan 01-03 used. Phase 2 closeout: all 10 DSP-* requirements landed across the three plans.**

## Performance

- **Duration:** ~10 min (plan start ~01:35Z; final task verify ~01:45Z)
- **Started:** 2026-04-29T01:35Z
- **Completed:** 2026-04-29
- **Tasks:** 4 of 4 complete
- **Files created:** 1 (`scripts/ats/preview.py`, 221 lines)
- **Files modified:** 1 (`skills/scout-run/SKILL.md`, +50 / -0)
- **Commits:** 2 (`1de5157` Task 1 preview.py; `f562cca` Task 3 SKILL.md)

## Files Modified

| File | Change | Lines | Commit |
|------|--------|-------|--------|
| `scripts/ats/preview.py` | created | +221 / -0 | `1de5157` |
| `skills/scout-run/SKILL.md` | modified (Step 2.5 inserted between Step 2 and Step 3) | +50 / -0 | `f562cca` |

Final commit (this metadata commit): `<this commit>` — adds SUMMARY.md, updates STATE.md, ROADMAP.md, REQUIREMENTS.md.

## Tasks Completed

- [x] **Task 1** — Create `scripts/ats/preview.py`. Single-fetch_all driver. Sibling-bootstrap (2-level). `run_preview(data_dir, today, slugs, provider='greenhouse')` function + CLI dispatch. Empty-slugs roundtrip appends exactly ONE runs.jsonl line + writes ZERO ats_raw files. Verified: `--help` mentions "ONE process"; `--version` prints "Phase 2 DSP-10 driver, v0.4"; `grep -c 'fetch_all('` = 1. Commit `1de5157`.
- [x] **Task 2** — Detect + snapshot user's pending uncommitted edits to `skills/scout-run/SKILL.md`. Snapshot saved to `/tmp/scout-run-SKILL-pre-DSP10.md`; `git diff` saved to `/tmp/scout-run-SKILL-pending-DSP10.diff` (29 lines = 2 hunks + diff metadata). HAS_PENDING=1 confirmed. No commit (pure protocol setup).
- [x] **Task 3** — Reset working tree to HEAD; apply Plan 02-03's [ATS-PREVIEW] edit on a clean base via the Edit tool (anchor: `## Step 3: Pass 2 — Other job boards (≈25% of budget)` heading); commit. Verified: `git diff HEAD~1 HEAD` shows ONLY Plan 02-03's hunk (no f_C content); `grep -c 'fetch_all('` in committed SKILL.md = 0. Commit `f562cca`.
- [x] **Task 4** — Restore user's pending snapshot to working tree (`/bin/cp` from `/tmp`); re-apply Plan 02-03's [ATS-PREVIEW] edit on top via the same Edit tool old_string/new_string pair (anchor identical in both versions). Verified: working tree contains BOTH Plan 02-03's Step 2.5 AND user's frontmatter 0.3.3 + f_C-disabled hunks; `git diff` against HEAD shows ONLY user's 2 hunks (50-line difference between working tree and snapshot is exactly Plan 02-03's block). `/tmp` files cleaned up. No commit (user's edits remain uncommitted).

## Verify Results

All 7 plan-level smoke gates passed:

```
=== GATE 1: Plan 02-03 commit landed ===
OK
=== GATE 2: preview.py exists + ONE fetch_all call ===
preview.py exists
fetch_all paren count <=2 OK
--help OK
=== GATE 3: SKILL.md Step 2.5 wiring ===
Step 2.5 in HEAD OK
preview.py path in HEAD OK
runs_log.append_run in HEAD OK
ats_raw in HEAD OK
=== GATE 4: SKILL.md ZERO inline fetch_all calls (DSP-03 invariant) ===
fetch_all paren count = 0 OK
=== GATE 5: User's pending edits preserved in working tree ===
Plan 02-03 + user pending edits coexist in working tree OK
=== GATE 6: /tmp cleanup ===
/tmp clean OK
=== GATE 7: Phase 2 final substrate-roundtrip via preview.py (empty input, no network) ===
PHASE-2 PLAN-03 SMOKE: end-to-end preview.py empty roundtrip OK
```

Plus a CLI subprocess integration roundtrip:

```
{
  "outcome_count": 0,
  "wall_clock_seconds": 0.027,
  "per_provider_outcomes": {},
  "per_company_provider": {},
  "ok_with_results_companies": [],
  "raw_persisted": {}
}
runs.jsonl content:
{"timestamp":"2026-04-29T01:45:16Z","wall_clock_seconds":0.027,"providers":{},"per_company_provider":{}}
Exit code: 0
```

Compliance gates:

- `import asyncio` count in `scripts/ats/preview.py`: **0** (anti-feature honored)
- `import rapidfuzz` count in `scripts/ats/preview.py`: **0** (rapidfuzz is Phase 5)
- `--break-system-packages` count in `scripts/ats/preview.py`: **0** (CON-04 honored — preview.py has no install hint of its own; inherits from dispatcher.py's httpx ImportError block)
- `fetch_all(` count in `scripts/ats/preview.py`: **1** (the actual call; threat-model gate ≤2 honored)
- `fetch_all(` count in `skills/scout-run/SKILL.md` (HEAD): **0** (DSP-03 invariant at the SKILL boundary)
- New external dependencies: **0** (httpx already installed in Plan 02-01 Task 0)

## Stash-Replay Protocol Post-Mortem

**HAS_PENDING state at session start:** **1** (user had 2 pending uncommitted hunks in `skills/scout-run/SKILL.md` — frontmatter version 0.3.3 + Step 2 LinkedIn URL pattern with f_C-disabled rationale, totaling 9 inserted / 2 deleted lines).

**Protocol sequence executed:**

1. **Detect** (Task 2) — `git diff --quiet skills/scout-run/SKILL.md` exited non-zero → HAS_PENDING=1.
2. **Snapshot** (Task 2) — `/bin/cp` saved working tree to `/tmp/scout-run-SKILL-pre-DSP10.md`; byte-equality verified via `/usr/bin/diff -q`.
3. **Capture diff** (Task 2) — `git diff > /tmp/scout-run-SKILL-pending-DSP10.diff` (29 lines = 2 hunks + diff metadata), kept for post-mortem reference.
4. **Reset to HEAD** (Task 3) — `git checkout HEAD -- skills/scout-run/SKILL.md`. Confirmed clean via `git diff` (0 lines).
5. **Apply on clean base** (Task 3) — `Edit` tool with anchor `## Step 3: Pass 2 — Other job boards (≈25% of budget)` (unique in file, identical in HEAD and snapshot). Inserted Step 2.5 block.
6. **Commit on clean base** (Task 3) — `git commit -m 'feat(02-03): add [ATS-PREVIEW] Pass 1 hook ...'` → commit `f562cca`. Verified: `git diff HEAD~1 HEAD` contains only Plan 02-03's Step 2.5 hunk; no f_C content.
7. **Restore snapshot** (Task 4) — `/bin/cp /tmp/scout-run-SKILL-pre-DSP10.md skills/scout-run/SKILL.md`. Working tree now = HEAD~1 + user's hunks. `git diff` showed: removed Plan 02-03's 50 lines, added user's 9 lines.
8. **Re-apply on top** (Task 4) — `Edit` tool with the SAME old_string/new_string pair. Anchor matched at line 110 (offset by user's 7 added lines vs HEAD's line 103). Step 2.5 block inserted cleanly above Step 3.
9. **Verify final state** (Task 4) — `git diff skills/scout-run/SKILL.md` shows EXACTLY 2 hunks (user's frontmatter + LinkedIn URL pattern), zero remnants of Plan 02-03's edit (which is now in HEAD).
10. **Byte-identity check** (Task 4) — `/usr/bin/diff /tmp/...-pre-DSP10.md skills/scout-run/SKILL.md` shows exactly 50 lines added (the Step 2.5 block), 0 lines removed. The user's 9 lines of pending edits are byte-identical to the pre-Task-2 snapshot.
11. **Cleanup /tmp** (Task 4) — `/bin/rm -f /tmp/scout-run-SKILL-{pre,pending,HEAD}-DSP10.{md,diff}`. Verified absent.

**End state:**
- HEAD = `f562cca` (Plan 02-03's [ATS-PREVIEW] commit, on a clean HEAD~1 base; no f_C content).
- Working tree = HEAD + user's 2 pending hunks (frontmatter 0.3.3 + LinkedIn URL pattern).
- `git status --porcelain skills/scout-run/SKILL.md` = ` M skills/scout-run/SKILL.md` (uncommitted modifications, exactly as session-start).
- `/tmp` is clean.

**This is the second successful application of this protocol against this same file.** First was Plan 01-03 (commit 2e84994). Pattern is now established and reproducible.

## DSP-03 Single-Fetch_all Invariant Verification

The locked Phase 2 architectural anchor — exactly ONE shared `httpx.Client` per `/scout-run` — is preserved at TWO layers:

1. **Inside the dispatcher** (Plan 02-01): `fetch_all` opens the Client via `with httpx.Client(...) as client:` and passes it down to per-provider workers. ThreadPoolExecutor uses ONE shared Client across all worker threads (httpx Client is thread-safe).
2. **At the SKILL boundary** (Plan 02-03 — THIS plan): `skills/scout-run/SKILL.md` makes EXACTLY ONE Bash invocation per `/scout-run`: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/preview.py "<data_dir>" "<TODAY>" "<slugs_csv>"`. That single Python process calls `fetch_all` exactly once.

**Grep evidence (the threat-model T-02-18 mitigation):**

```
$ grep -c 'fetch_all(' scripts/ats/preview.py
1
```
(One paren form: line 130, the actual `outcomes = fetch_all(targets, config_path)` call. The import line `from ats.dispatcher import fetch_all, aggregate_outcomes` does not contain a paren. Docstring mentions use `fetch_all` no-paren form intentionally to keep the gate clean.)

```
$ git show HEAD:skills/scout-run/SKILL.md | grep -c 'fetch_all('
0
```
(ZERO inline heredoc fetch_all calls in the SKILL — the only mention is in prose where it describes what `dispatcher.fetch_all` does, no parens. The driver script invocation is the only entry point.)

**Iteration-1 BLOCKER 3 fix held.** The original plan draft had three SKILL bash steps (one for fetch_all, one for raw persistence, one for runs.jsonl append) — that would have instantiated three httpx.Clients per run, violating DSP-03. The driver-script collapse is the load-bearing fix.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring `fetch_all(` paren mentions exceeded grep gate threshold**

- **Found during:** Task 1 verify (the `test "$(grep -c 'fetch_all(' scripts/ats/preview.py)" -le 2` gate).
- **Issue:** Plan task action's verbatim docstring opener contained 4 mentions of `fetch_all(` with parens — three in the "Why a separate driver" paragraph (`fetch_all() owns`, `If the SKILL prompt called fetch_all() three times`) and one in the Behavior section (`Call dispatcher.fetch_all(targets, ...) ONCE`). Plus the actual call at line 130. Total = 4. Plan's verify gate is `≤ 2` (the import line + the actual call). The docstring mentions are documentation, not calls — but `grep -c` doesn't distinguish.
- **Fix:** Reworded docstring mentions to use `fetch_all` (no paren) where they're prose: `fetch_all owns the httpx.Client...`, `the SKILL prompt called the dispatcher three times`, `Call dispatcher.fetch_all with targets + config_path ONCE`, `Aggregate outcomes via dispatcher.aggregate_outcomes`, `Append ONE runs.jsonl line via runs_log.append_run`. Kept the actual call at line 130 with paren form (the only call). Also kept `--help` output's "ONE process -> ONE fetch_all -> ONE httpx.Client" prose (no parens).
- **Files modified:** `scripts/ats/preview.py` (docstring lines 7-8 and 32-37).
- **Verification:** Re-ran `grep -c 'fetch_all(' scripts/ats/preview.py` → 1 (the actual call). Verify gate passed.
- **Committed in:** `1de5157` (rolled into the same Task 1 commit; the docstring tweak was applied before the file was first staged).

---

**Total deviations:** 1 auto-fixed ([Rule 1 - Bug])
**Impact on plan:** Cosmetic docstring change preserving DSP-03 verifiability through `grep -c 'fetch_all('`. Behavior unchanged. Net effect: the threat-model T-02-18 mitigation gate (≤2) is satisfied with a margin (actual = 1).

## Issues Encountered

- **None outside the one Rule-1 auto-fix above.** All 7 plan-level smoke gates passed; CLI subprocess roundtrip succeeded; stash-replay protocol completed cleanly with byte-identical snapshot preservation.

## Authentication Gates

None. preview.py operates on local file paths only (Phase 2 has no Greenhouse data in master_targets.csv yet — the empty-slugs roundtrip is what the SKILL exercises today).

## User Setup Required

None. preview.py inherits httpx from dispatcher.py's import (already installed in `~/.job-scout-venv` in Plan 02-01 Task 0). End users hit the dispatcher's CON-04-compliant ImportError install hint at runtime if httpx is missing.

The `[ATS-PREVIEW]` block in /scout-run will start producing real network output starting in Phase 3, after `/scout-detect` populates `ats_provider="greenhouse"` for top-30 companies in `master_targets.csv`. Until then, the block invokes preview.py with `<slugs_csv>=""` and a 0-outcome runs.jsonl heartbeat is appended (intentional design — Phase 5's regression-suspect detection needs the daily heartbeat from day one).

## Phase 2 Closeout — All 10 DSP-* Requirements Landed

| Requirement | Plan | Description | Verified by |
|---|---|---|---|
| DSP-01 | 02-01 | Provider Protocol via `typing.Protocol` with `@runtime_checkable` (no inheritance) | `scripts/ats/providers/base.py` |
| DSP-02 | 02-01 | `Listing.__post_init__` raises ValueError on missing required field | `scripts/ats/normalize.py` |
| DSP-03 | 02-01 + **02-03** | ONE shared `httpx.Client` per `/scout-run` (dispatcher-internal AND SKILL-boundary) | `scripts/ats/dispatcher.py` `with httpx.Client(...) as client:` + `grep -c 'fetch_all(' skills/scout-run/SKILL.md == 0` |
| DSP-04 | 02-01 | `ThreadPoolExecutor(max_workers=20)` + per-provider `threading.Semaphore` from `config.json` | `scripts/ats/dispatcher.py` `_init_semaphores` + `_gate` |
| DSP-05 | 02-01 | Three-state outcomes: `OK_WITH_RESULTS` / `OK_ZERO` / `ERROR` (single-source enum in `runs_log.py`) | `scripts/ats/runs_log.py` `RunOutcome` enum |
| DSP-06 | 02-01 | Two-tier exception handling: re-raise unrecoverable; bucket recoverable as ERROR | `scripts/ats/dispatcher.py` `_execute_one` |
| DSP-07 | 02-01 + **02-03** | Append-only `runs.jsonl` writer with per-(company, provider) hit counts + field_completion telemetry; ONE append per run from preview.py | `scripts/ats/runs_log.py` `append_run` + `scripts/ats/preview.py` single `append_run` call |
| DSP-08 | 02-01 | `ats.concurrency_disabled` kill-switch in `config.json` (sequential fallback) | `scripts/ats/dispatcher.py` `load_caps_and_kill_switch` + sequential branch |
| DSP-09 | 02-02 | Greenhouse provider conforming to Provider Protocol; airbnb 3-job sanitized fixture; SC-4 broken-fixture stress test | `scripts/ats/providers/greenhouse.py` + `tests/fixtures/ats/greenhouse/airbnb.json` + `scripts/ats/__init__.py:PROVIDERS["greenhouse"]` |
| DSP-10 | **02-03** | `[ATS-PREVIEW]` Pass 1 wire-in to `/scout-run` Step 2.5 + `runs.jsonl` append + `ats_raw/<provider>/<slug>.json` persistence; stash-replay protocol | `scripts/ats/preview.py` + `skills/scout-run/SKILL.md` Step 2.5 + protocol post-mortem above |

**All 10 requirements verifiable from the codebase:** the dispatcher tests pass on empty input; the Greenhouse provider passes its fixture roundtrip; preview.py passes the empty-slugs roundtrip and writes one runs.jsonl line per invocation. Phase 2's substrate is complete.

## Hand-off to Phase 3 (Detection + /scout-detect + lazy inline)

Phase 2 ships the substrate; Phase 3 starts populating it. The hand-off:

- **`PROVIDERS["greenhouse"]`** is callable: `fetch_all([(slug, "greenhouse")], cfg)` returns one `OK_WITH_RESULTS / OK_ZERO / ERROR` `FetchOutcome` per target. Phase 3's `/scout-detect` can also use `PROVIDERS["greenhouse"].detect(slug, name, client)` — currently returns BORDERLINE on 200+jobs (awaits Phase 3's `rapidfuzz` name fuzzy-match layer for full CONFIRMED status).
- **`scripts/ats/preview.py`** is the canonical /scout-run entry point. Phase 3's `/scout-detect` is a separate skill — its CLI counterpart should follow the same SINGLE-driver pattern (one process per skill invocation, one httpx.Client lifetime).
- **`runs.jsonl` daily heartbeat** is appended starting today (per /scout-run that runs Step 2.5). Phase 5's regression-suspect detection has a baseline to compare against from day one.
- **`master_targets.csv` schema v=4** has `ats_provider` and `ats_board_url` columns waiting for `/scout-detect` to populate. Phase 1 verified the migration round-trip works.
- **Anti-feature reminder for Phase 3 planning**: do NOT add a generic ATS abstraction layer on top of PROVIDERS. Per-provider modules stay 100-200 lines each. The Provider Protocol is the abstraction.
- **Phase 3 is flagged for `/gsd-research-phase` per ROADMAP.md** — not because of unknowns about the substrate (substrate is locked), but because of the two-factor detection gate's tuning (200 + ≥1 job + name fuzzy match ≥85%) which needs real data from a top-30 batch run.

## Threat Flags

No new security-relevant surface introduced beyond what Plan 02-01's threat model already covered. preview.py is a thin process boundary — no new network endpoints (it delegates to dispatcher.py); no new file paths outside `<data_dir>/{runs.jsonl, daily/<TODAY>/ats_raw/<provider>/<slug>.json}` already in `file-contract.md` (Phase 1 SCH-01/02); no new auth surfaces.

## Self-Check: PASSED

- Created file exists on disk: `scripts/ats/preview.py` — `test -f` confirmed (221 lines).
- Modified file in HEAD has Step 2.5 block: `git show HEAD:skills/scout-run/SKILL.md | grep -q "## Step 2.5: \[ATS-PREVIEW\]"` confirmed.
- Both task commits exist in git log:
  - `1de5157` — feat(02-03): add scripts/ats/preview.py — single-fetch_all driver for [ATS-PREVIEW] (DSP-10)
  - `f562cca` — feat(02-03): add [ATS-PREVIEW] Pass 1 hook to /scout-run Step 2.5 (DSP-10)
- All 7 plan-level smoke gates passed. CLI subprocess integration roundtrip passed.
- Stash-replay protocol final-state byte-identity to pre-Task-2 snapshot confirmed (working tree = snapshot + 50 lines = the new Step 2.5 block; user's 9 lines of pending edits are byte-identical).
- `/tmp` cleanup confirmed (3 files removed).
- DSP-03 single-fetch_all invariant: `grep -c 'fetch_all(' scripts/ats/preview.py == 1` (the actual call); `grep -c 'fetch_all(' skills/scout-run/SKILL.md == 0` in HEAD.
- Compliance gates passed: zero asyncio, zero rapidfuzz, zero `--break-system-packages`, zero new external dependencies.

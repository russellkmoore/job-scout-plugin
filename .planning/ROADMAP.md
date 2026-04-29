# Roadmap: job-scout-plugin v0.4 — ATS-first job sourcing

**Created:** 2026-04-27
**Milestone:** v0.4
**Granularity:** standard (6 phases)
**Coverage:** 51/51 v1 requirements mapped

## Milestone Bar

A v0.4 release is "done" only when all four are simultaneously true, verified from `<data_dir>/runs.jsonl`:

1. 5-run rolling Pass-1 (ATS) share ≥ 60% of A/B-tier candidates
2. `/scout-run` wall-clock ≤ 5 minutes (5-run average)
3. Zero references to marketing-page Chrome scraping in `skills/` or `scripts/`
4. Every listing in `report.md` carries a `source=` tag

Phase 6 explicitly verifies (1) and (2). Phases 2–5 establish the observability that makes them measurable. Phase 6 enforces (3) and (4).

## Phases

- [x] **Phase 1: Schema migration + paths + foundational cleanup** — Bump master_targets to v=4 (add `ats_slug_confidence`, `last_ats_hit_date`), add tracker `source` + `ats_provider` columns, create `runs.jsonl` and `daily/<DATE>/ats_raw/` paths, ship the v3→v4 fixture migration test, **and** absorb the foundational concerns cleanup that touches the same scripts: fix the `consolidate_targets.py:270` KeyError, add the `application_status` enum, harden `mine_connections.py` header detection, switch `--break-system-packages` install hints to `pipx`/venv, resolve the `LEGACY_DATA_DIRS` contradiction, align the `companies_per_day` default drift, and harden `~/.job-scout/` file permissions.
- [x] **Phase 2: Provider Protocol + Greenhouse end-to-end + dispatcher + observability foundations** — Vertical slice: build the Provider Protocol, the canonical `Listing`, the concurrent dispatcher (httpx, semaphores, kill-switch, three-state errors), `runs.jsonl` writer with per-(company, provider) telemetry, and Greenhouse as the first conformant provider. Wire into `/scout-run` additively as `[ATS-PREVIEW]`.
- [x] **Phase 3: Detection + `/scout-detect` skill + lazy inline detect + dead-doc-ref cleanup** — Two-factor gate detection, negative-result caching, borderline-review CSV, the new `/scout-detect` skill for top-30 batch detection, and lazy inline detection during `/scout-run`. Slug-confidence column populated; manual lock honored. **Also fixes the 3 dead `commands/scout-run.md` references in the same skill-doc files being modified for the new skill.**
- [x] **Phase 4: Remaining providers (Lever, Ashby, SmartRecruiters, Workday) + JSON-LD fallback + filtering layer** — Four more provider modules conforming to the Protocol, JSON-LD fallback as a sixth virtual provider, per-provider posted-date overrides, intra-source regional collapse, evergreen-title blocklist, Workday CSRF/auth-required explicit detection.
- [x] **Phase 5: Cross-source dedup + ATS tier bump + enrich-then-tier + scoring/tracker cleanup** — Tiered confidence band + two-key fuzzy dedup of Pass 2 against Pass 1, conditional +1 ATS tier bump (≤30d), LinkedIn shared-connection enrichment for ATS A-candidates only, ATS regression-suspect warnings in report's *Honest notes*. Chrome MCP scoped to LinkedIn-only. **Also absorbs the scoring-rubric and tracker-utils cleanup landing on the same surfaces:** rewrite the dead `pipeline_tier` Pass-1 priority and +5 bonus, add LinkedIn rate-limit/backoff to enrichment, make LinkedIn JD lazy-load resilient, split `extract_job_id` into `extract_linkedin_job_id` + `extract_dedup_key`, rename `skipped_stale` → `flagged_stale_count`, add Pass-2 board-broken warnings, and preserve user-added xlsx columns in `_write_tracker`.
- [x] **Phase 6: Run summary + delete legacy + milestone close + version/PII/post-run cleanup** — Run-summary block at top of `report.md` and on stdout, complete deletion of marketing-page Chrome scraping (verified by grep), trimmed `chrome-setup.md`, version bump to 0.4.0, README update, and verification of the milestone bar (5-run rolling Pass-1 share ≥ 60%, wall-clock ≤ 5 min). **Also absorbs the cross-cutting close-out cleanup:** normalize plugin/skill version sprawl in lockstep, delete the inline column list in `skills/job-scout/SKILL.md:38`, add PII handling note + `.gitignore` template entry to `/scout-setup`, and ship a post-write validation check at end of `/scout-run` Step 6.

## Phase Details

### Phase 1: Schema migration + paths + foundational cleanup

**Goal**: User's `master_targets.csv`, tracker xlsx, and `runs.jsonl` are upgraded to the v0.4 shape with zero data loss, the migration is locked behind a fixture test, and the foundational tech-debt items in `scripts/` (the dead `consolidate_targets.py:270` KeyError, magic-string `application_status` drift, fragile `mine_connections.py` header detection, `--break-system-packages` install hints, the `LEGACY_DATA_DIRS` contradiction, the `companies_per_day` default drift, and unhardened state.json permissions) are fixed in the same commits that touch those files. Every later phase builds on a clean substrate.

**Depends on**: Nothing (first phase)

**Requirements**: SCH-01, SCH-02, SCH-03, SCH-04, SCH-05, SCH-06, CON-01, CON-02, CON-03, CON-04, CON-05, CON-06, CON-07

**Success Criteria** (what must be TRUE):
  1. A user with a v0.3 `master_targets.csv` can run `/scout-run` and the file is upgraded to v=4 in place — `ats_slug_confidence` and `last_ats_hit_date` columns appear, every existing row is preserved, and any user-added columns survive at the end.
  2. After Phase 1 ships, the user's `JobScout_Tracker.xlsx` shows `source` and `ats_provider` columns and existing rows are populated as empty (back-compatible — older Excel filters still work).
  3. `python3 -m pytest tests/test_migration.py` passes against the checked-in `tests/fixtures/master_targets_v3.csv` and asserts (a) all v3 rows preserved, (b) new columns present + empty, (c) v0.3 code path can still read the resulting v4 CSV without crash.
  4. Running `/scout-run` on a fresh setup produces empty `<data_dir>/runs.jsonl` and `<data_dir>/daily/<DATE>/ats_raw/` directory before any ATS code executes.
  5. `references/file-contract.md` lists `runs.jsonl` and `daily/<DATE>/ats_raw/` as the canonical paths — no other file describes them.
  6. `python3 scripts/consolidate_targets.py --output … --files …` runs end-to-end without `KeyError: 'already_applied'` (CON-01); a tracker append with `application_status="dad"` (typo) is rejected by the new `STATUS_VALUES` enum (CON-02); `mine_connections.py` against a Spanish-localized export logs a warning instead of silently skipping 3 connections (CON-03).
  7. Every `ImportError` in `scripts/` (and the new `scripts/ats/*`) recommends `pipx`/venv instead of `pip install --break-system-packages` (CON-04); `~/.job-scout/state.json` is created with mode `0o600` and `~/.job-scout/` with `0o700` (CON-07); `LEGACY_DATA_DIRS` is either gone (with a one-time `/scout-setup` migration prompt) or `file-contract.md` is updated to acknowledge the fallback chain — pick one (CON-05); a single `companies_per_day` default exists in exactly one place across `templates/config.json`, `scout-run/SKILL.md`, and `search-config.md` (CON-06).

**Plans**: 4 plans

- [x] 01-01-PLAN.md — Schema bump (v=4) + STATUS_VALUES + validate_data wiring + tracker xlsx 16-col extension
- [x] 01-02-PLAN.md — state.py legacy chain + perm hardening + consolidate_targets dead block + mine_connections header guard + install hints (2 of 4)
- [x] 01-03-PLAN.md — file-contract.md path entries + companies_per_day SSOT consolidation + scout-setup legacy-dir migration prompt
- [x] 01-04-PLAN.md — Migration round-trip pytest (tests/test_migration.py + fixture) + phase-wide grep gate

### Phase 2: Provider Protocol + Greenhouse end-to-end + dispatcher + observability foundations

**Goal**: A user running `/scout-run` sees Greenhouse-sourced listings appearing in their daily report behind an `[ATS-PREVIEW]` tag, alongside the existing 3-pass flow, and can inspect per-company, per-provider counts in `runs.jsonl` from day one.

**Depends on**: Phase 1

**Requirements**: DSP-01, DSP-02, DSP-03, DSP-04, DSP-05, DSP-06, DSP-07, DSP-08, DSP-09, DSP-10

**Success Criteria** (what must be TRUE):
  1. After running `/scout-run` against a `master_targets.csv` containing at least 3 known-Greenhouse companies, the user sees Greenhouse listings in their daily report tagged `[ATS-PREVIEW] source=ats:greenhouse` — and the existing 3-pass output is still present (additive, non-breaking).
  2. The user can `tail -1 <data_dir>/runs.jsonl | jq` and see one JSON line per run with `wall_clock_seconds`, per-provider counts of `ok_with_results`/`ok_zero`/`error`, per-(company, provider) listing counts, and field-completion telemetry — proving the trust-on-zero decision is auditable from day one.
  3. The user can flip `ats.concurrency_disabled: true` in `config.json` and the next `/scout-run` produces the same output but runs sequentially (proving the kill-switch works without code change).
  4. A deliberately-broken Greenhouse fixture (raises during `to_listing()`) surfaces as a logged exception in `runs.jsonl` with the `(company, provider)` context — never silently swallowed.
  5. Running `/scout-run` against a target list of 30 Greenhouse companies + 1 Lever stub never opens more than 10 simultaneous Greenhouse connections (per-provider semaphore enforced, not global cap masquerading).

**Plans**: 3 plans

- [x] 02-01-dispatcher-PLAN.md — scripts/ats package skeleton + Provider Protocol + Listing dataclass + dispatcher (shared httpx.Client + per-provider semaphores + 3-state outcomes + kill-switch) + runs_log.py append-only writer (DSP-01..08)
- [x] 02-02-greenhouse-PLAN.md — Greenhouse provider conforming to Provider Protocol + checked-in sanitized fixture (airbnb 3-job slice) + smoke roundtrip via fixture (DSP-09)
- [x] 02-03-wire-preview-PLAN.md — Wire [ATS-PREVIEW] Pass 1 hook into /scout-run Step 2.5 + runs.jsonl append + ats_raw/<provider>/<company>.json persistence; preserves user's pending uncommitted edits via stash-replay protocol (DSP-10)

### Phase 3: Detection + `/scout-detect` skill + lazy inline detect + dead-doc-ref cleanup

**Goal**: A user with a fresh `master_targets.csv` can run `/scout-detect` once to populate `ats_provider`, `ats_board_url`, and `ats_slug_confidence` for their top-30 connection-weighted companies, and any company missing an `ats_provider` is auto-detected the next time `/scout-run` includes it — with false-positive guards that prevent scraping the wrong company. While we're editing the same skill-doc files to introduce `/scout-detect`, the 3 dead `commands/scout-run.md` references (the `commands/` directory was removed in commit `1d31872`) are also fixed in those same edits.

**Depends on**: Phase 2 (uses dispatcher + Greenhouse provider as the validation backbone)

**Requirements**: DET-01, DET-02, DET-03, DET-04, DET-05, DET-06, DET-07, STR-02, STR-04, CON-08

**Success Criteria** (what must be TRUE):
  1. The user runs `/scout-detect` and sees their top-30 companies' `ats_provider` and `ats_board_url` fields populated in `master_targets.csv` — with `ats_slug_confidence` showing 1.0 for two-factor-confirmed matches and 0.7–0.94 for borderline ones.
  2. A deliberately-injected wrong-company collision (e.g., pointing detection at a generic slug like `acme` known to belong to a different company) is rejected by the two-factor gate (200 + ≥1 job + name fuzzy match ≥85%) — and the user sees no false-positive write to `master_targets.csv`.
  3. Re-running `/scout-detect` on the same CSV is a no-op (skips rows where `ats_provider` is non-empty); passing `--force` re-detects; rows with `ats_provider=manual` are never overwritten regardless of `--force`.
  4. Borderline matches (gate score 70–84) appear in `<data_dir>/ats_detection_review.csv` with company, provider, score, and proposed `ats_board_url` — the user can review and either accept (manual edit) or skip without re-running detection.
  5. During `/scout-run`, any company in the day's slate with empty `ats_provider` triggers inline detection via the same `detect-one` code path, and the result is written back to `master_targets.csv` after the run — no re-detection on subsequent runs.
  6. `grep -rn "commands/scout-run.md" skills/` returns zero matches (CON-08); the 3 doc references at `skills/job-scout/SKILL.md:46`, `skills/job-scout/SKILL.md:105`, `skills/job-scout/references/search-config.md:28` now point at `skills/scout-run/SKILL.md`.

**Plans**: 3 plans

Plans:
- [ ] 03-01-PLAN.md — detect.py + rapidfuzz install + tests/test_detection.py + ats_detection_review.csv writer (DET-01..05, DET-07, STR-02, STR-04)
- [ ] 03-02-PLAN.md — /scout-detect SKILL.md + ats_detection_review.csv added to file-contract.md (DET-06, STR-02, STR-04)
- [ ] 03-03-PLAN.md — /scout-run Step 2b lazy inline detect + 3 CON-08 dead-doc-ref rewrites (DET-04, DET-07, CON-08)

### Phase 4: Remaining providers (Lever, Ashby, SmartRecruiters, Workday) + JSON-LD fallback + filtering layer

**Goal**: Pass 1 covers all five committed ATS providers plus a JSON-LD fallback for ATS-undetected companies, with stale/regional/evergreen postings filtered out and Workday auth-required tenants explicitly logged (not silently zeroed).

**Depends on**: Phase 3 (detection must populate provider columns before fetch can iterate them)

**Requirements**: PRV-01, PRV-02, PRV-03, PRV-04, PRV-05, PRV-06, PRV-07, PRV-08, PRV-09, STR-01, STR-03

**Success Criteria** (what must be TRUE):
  1. A user with a mixed `master_targets.csv` (companies on Greenhouse, Lever, Ashby, SmartRecruiters, and Workday) sees listings from all five providers in their daily report, each tagged `source=ats:<provider>` — with no provider named in dispatcher or skill code (registry-driven).
  2. A Workday tenant requiring CSRF/session tokens appears in `runs.jsonl` as `workday-auth-required` and the company is routed to Pass 2 explicitly — not silently bucketed as `OK_ZERO`.
  3. For ATS-undetected companies whose `master_targets.csv` row has a `careers_url`, JSON-LD `JobPosting` blocks on that page are fetched once via `httpx`, normalized to `Listing`, and appear in the report tagged `source=ats:jsonld` — without any Chrome navigation.
  4. The report no longer contains evergreen "Talent Network"/"General Application"/"Future Opportunities" entries, no stale (>60d default) postings, and no regional duplicates of the same role from the same provider — verified by spot-check on a Workday tenant known to post US/UK/EU variants.
  5. The user can override `ats.posted_date_max_age_days` per provider in `config.json` (e.g., Workday=90, Greenhouse=30) and the filter respects the override at next run.

**Plans**: 5 plans

Plans:
- [ ] 04-01-PLAN.md — Wave 0 scaffolding: base.py auth_required field + detect.py D-3 skip guard + tests/test_providers_phase4.py (15 RED tests) + 5 fixture sets (PRV-05, PRV-09, STR-01)
- [ ] 04-02-PLAN.md — Lever + Ashby providers (PRV-01, PRV-02)
- [ ] 04-03-PLAN.md — SmartRecruiters + Workday providers + Workday CSRF detection (PRV-03, PRV-04, PRV-05)
- [ ] 04-04-PLAN.md — JSON-LD virtual provider (STR-01)
- [ ] 04-05-PLAN.md — normalize.py filters + PROVIDERS registry wiring + dispatcher auth_required reason + preview.py apply_filters + templates/config.json ats section (PRV-05, PRV-06, PRV-07, PRV-08, PRV-09, STR-03)

### Phase 5: Cross-source dedup + ATS tier bump + enrich-then-tier + scoring/tracker cleanup

**Goal**: When a role appears in both Pass 1 (ATS) and Pass 2 (LinkedIn), the user sees one row, not two; ATS-sourced A-candidates carry shared-connection enrichment from LinkedIn; A/B-tier postings reflect the +1 ATS bump for fresh listings; and any company with a sudden ATS hit-count regression appears in the report's *Honest notes*. While we're rewriting `scoring-rubric.md`, `scout-run/SKILL.md`, and `tracker_utils.py` for dedup/tier/enrich, the related concerns also land in those same edits: the dead `pipeline_tier` references in scoring (CON-09, CON-10), LinkedIn rate-limit/backoff in enrichment (CON-11), JD lazy-load resilience (CON-12), `extract_job_id` split + caller migration (CON-13), `skipped_stale` rename (CON-14), Pass-2 board-broken warnings (CON-15), and `_write_tracker` user-column preservation (CON-20).

**Depends on**: Phase 4 (needs multi-provider Pass 1 + Pass 2 data to dedupe and enrich against)

**Requirements**: DDP-01, DDP-02, DDP-03, DDP-04, DDP-05, DDP-06, DDP-07, DDP-08, CON-09, CON-10, CON-11, CON-12, CON-13, CON-14, CON-15, CON-20

**Success Criteria** (what must be TRUE):
  1. When the same role appears in Pass 1 (e.g., Stripe Greenhouse) and Pass 2 (LinkedIn keyword search), the daily report contains exactly one merged row tagged `source=ats:greenhouse` — not two — and `runs.jsonl` shows the dedup decision with both source IDs and the title-similarity score.
  2. Borderline dedup matches (70–94% similarity, or only one of the two keys agreeing) appear in the report's *Honest notes* as "possible duplicates flagged" — never silently auto-merged or auto-kept.
  3. An ATS-sourced posting ≤30 days old shows a +1 tier bump in its score breakdown (e.g., `score: 87 (base 82, +5 connection, +1 ATS warm path)`); ATS postings >30 days old get no bump.
  4. Every ATS A-tier candidate in the report carries a "Connections" field with shared-connection count + top 3 named connections, captured via Chrome MCP navigation to LinkedIn — and `grep -ri "career_page\|marketing-page" skills/scout-run/SKILL.md` returns zero matches (Chrome scoped to LinkedIn only).
  5. Any company that returned `OK_WITH_RESULTS` for ≥3 of the last 5 runs but `OK_ZERO`/`ERROR` today appears in the report's *Honest notes* as "ATS regression suspect" — proving the trust-on-zero decision is defended by visible warnings.
  6. `grep -rn "pipeline_tier" skills/` returns zero matches (CON-09, CON-10) — the Pass-1 priority order in `search-config.md:52` and the +5 bonus row in `scoring-rubric.md:111` now reference `linkedin_connection_count` thresholds. A career-page URL `https://acme.com/careers/job/2024100912345` no longer trips the LinkedIn stale-flag (CON-13: `extract_linkedin_job_id` returns `None` for non-LinkedIn URLs); a user xlsx column outside `TRACKER_COLUMNS` survives a tracker append round-trip (CON-20).
  7. The new enrichment step inserts a 10–15s pause between every 5th LinkedIn navigation (CON-11); a deliberately-stripped LinkedIn JD page (no `...more` button matching the primary selector) is recovered via secondary selector + length-check retry, and the failure (if it ultimately occurs) appears in `runs.jsonl` (CON-12); a Pass-2 board returning 0 results for ≥3 of the last 5 runs surfaces a "board appears broken" line in the report's *Honest notes* (CON-15); and the local variable `flagged_stale_count` matches the returned dict key in `tracker_utils.py` (CON-14).

**Plans**: 5 plans

Plans:
- [ ] 05-01-PLAN.md — Wave 0: tests/test_dedup_phase5.py + tests/test_tracker_phase5.py + 5 fixtures (RED scaffold for DDP-01..08, CON-09..15, CON-20)
- [ ] 05-02-PLAN.md — scripts/ats/dedupe.py (two-key tiered fuzzy dedup + ATS tier bump + LinkedIn slug + enrichment-scope helper) + templates/config.json dedup.thresholds (DDP-01..05)
- [ ] 05-03-PLAN.md — scripts/tracker_utils.py surgery: split extract_job_id, rename skipped_stale (Pitfall 6), preserve user xlsx columns (CON-12 marker, CON-13/14/20)
- [ ] 05-04-PLAN.md — scripts/ats/runs_log.py extensions: D-2 telemetry kwargs + regression-suspects + pass2-board-broken CLI subcommands (DDP-04/06/07/08)
- [ ] 05-05-PLAN.md — skills/scout-run/SKILL.md flow rewrite (Step 2.5 JSON-LD + Step 4.5 dedup + Step 5 enrich-then-tier + Step 6 Honest notes) + scoring-rubric.md/search-config.md/chrome-setup.md doc fixes (DDP-05..08, CON-09..12, CON-15)

### Phase 6: Run summary + delete legacy + milestone close + version/PII/post-run cleanup

**Goal**: The marketing-page Chrome scraping path is gone, every report opens with a Pass-1 share + wall-clock summary block, the plugin ships as v0.4.0, and the milestone bar is verified across 5 real runs. The cross-cutting close-out cleanup also lands here, on the same files being touched for v0.4.0 release: plugin and skill versions normalized in lockstep (CON-16), the inline column list in `skills/job-scout/SKILL.md:38` deleted in favor of "see schema.py" (CON-17), PII handling note + `.gitignore` template entry added to `/scout-setup` (CON-18, CON-19), and a post-write validation check added at the end of `/scout-run` Step 6 (CON-21).

**Depends on**: Phase 5 (legacy deletion is only safe once Pass 1 + dedup + enrich all produce reliable output)

**Requirements**: OUT-01, OUT-02, OUT-03, OUT-04, OUT-05, OUT-06, OUT-07, CON-16, CON-17, CON-18, CON-19, CON-21

**Success Criteria** (what must be TRUE):
  1. Every listing in `report.md` and every row in `JobScout_Tracker.xlsx` carries a `source=` annotation (`ats:greenhouse|ats:lever|ats:ashby|ats:smartrecruiters|ats:workday|ats:jsonld|linkedin`) — verifiable by `grep -c 'source=' <data_dir>/daily/<DATE>/report.md` matching the listing count.
  2. The first block of `report.md` and the last lines of stdout from `/scout-run` show: total listings, A/B/C counts, Pass-1 share %, total wall-clock seconds, per-provider breakdown (count + ok_zero + error), and top 3 ATS regression warnings if any — visible in scheduled-run logs without opening the report file.
  3. `grep -ri "career_page\|careers-html\|marketing-page" skills/ scripts/` returns zero matches; `chrome-setup.md` no longer mentions career-page setup; the existing Chrome scraping code path is gone (not commented out, not flagged — deleted).
  4. `.claude-plugin/plugin.json` shows `"version": "0.4.0"` and **every** `skills/*/SKILL.md` `version:` frontmatter field also shows `0.4.0` — verifiable by `grep -h "^version:" skills/*/SKILL.md` returning exactly four `0.4.0` lines (CON-16); `README.md` has a v0.4 section explaining the ATS-first flow and the new `/scout-detect` skill.
  5. The 5-run rolling average of Pass-1 share computed from the last 5 lines of `<data_dir>/runs.jsonl` is ≥60%; the average `wall_clock_seconds` across the same 5 entries is ≤300 — both verifiable with a single `jq` one-liner before declaring v0.4 complete.
  6. `skills/job-scout/SKILL.md:38` no longer lists schema columns inline (CON-17) — replaced with "see `scripts/schema.py:MASTER_TARGETS_COLUMNS`"; `/scout-setup` Step 1 includes a PII warning naming `connections_summary.csv` and `master_targets.csv:connection_names`, and explicitly cautions against placing `<data_dir>` in iCloud/Dropbox/OneDrive (CON-18); a `.gitignore` template plus a "redact `resume_path` before sharing" warning is documented (CON-19).
  7. A `/scout-run` invocation that errors mid-Step 6 surfaces a `WARNING: post-run validation failed: <reason>` line on stdout naming the missing artifact (`report.md`, `runs.jsonl`, or A-tier count mismatch) — verifiable by force-killing scout-run after Step 5 in a test environment (CON-21).

**Plans**: 5 plans

Plans:
- [ ] 06-01-PLAN.md — Wave 0 RED tests: tests/test_runs_log_phase6.py (5 tests for compute_milestone_bar + milestone-bar CLI + edges; OUT-07 RED scaffold)
- [ ] 06-02-PLAN.md — scripts/ats/runs_log.py extensions: compute_milestone_bar helper + milestone-bar CLI subcommand + ab_tier_counts optional kwarg in append_run (D-1, D-2 — turns Plan 06-01 RED to GREEN; OUT-07)
- [ ] 06-03-PLAN.md — Doc + version cleanup bundle: job-scout/SKILL.md inline column list deletion, scout-setup/SKILL.md PII callout + .gitignore template, scout-detect/SKILL.md line 153 reword, chrome-setup.md verify, plugin.json version + description, README v0.4 capabilities section (OUT-04, OUT-05, OUT-06, CON-16 [3-of-4 SKILL.md], CON-17, CON-18, CON-19)
- [ ] 06-04-PLAN.md — scout-run/SKILL.md integration: Step 2 marketing-page deletion (P1, P3), Step 2.5 banner cleanup (P2), Step 5 ab_tier_counts write (D-1, P4), Step 6 Run Summary block (OUT-01, OUT-02), Step 7.5 post-write validation (CON-21, P7), Step 9 stdout mirror (OUT-03), version bump + preview.py docstring cleanup (OUT-01..04, CON-16 [final SKILL.md], CON-21)
- [ ] 06-05-PLAN.md — Phase-wide grep gate: tests/test_phase6_grep_gate.py (9 pytest assertions encoding VALIDATION.md gate — [ATS-PREVIEW]=0, marketing-page=0, version lockstep=4, milestone-bar CLI smoke; OUT-03..07, CON-16..19, CON-21)

## Phase Dependencies

```
Phase 1 (schema + paths + migration test)
    ↓
Phase 2 (Provider Protocol + Greenhouse + dispatcher + runs.jsonl)
    ↓
Phase 3 (Detection + /scout-detect + lazy inline)
    ↓
Phase 4 (Remaining providers + JSON-LD + filtering)
    ↓
Phase 5 (Cross-source dedup + tier bump + enrich + regression warnings)
    ↓
Phase 6 (Run summary + delete legacy + milestone close)
```

Strictly linear. Each phase consumes the artifacts of the previous one. No phase can begin until the prior phase's success criteria are met.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Schema migration + paths + foundational cleanup | 4/4 | Complete | 2026-04-28 |
| 2. Provider Protocol + Greenhouse + dispatcher + observability | 3/3 | Complete | 2026-04-29 |
| 3. Detection + /scout-detect + lazy inline + dead-doc-ref cleanup | 3/3 | Complete | 2026-04-29 |
| 4. Remaining providers + JSON-LD + filtering | 5/5 | Complete | 2026-04-29 |
| 5. Cross-source dedup + tier bump + enrich + scoring/tracker cleanup | 5/5 | Complete | 2026-04-29 |
| 6. Run summary + delete legacy + milestone close + version/PII/post-run cleanup | 5/5 | Complete | 2026-04-29 |

## Coverage

- v1 requirements: 72 total (51 ATS feature + 21 concerns cleanup)
- Mapped to phases: 72 (100%)
- Unmapped: 0

| Category | Phase | Count |
|----------|-------|-------|
| SCH (Schema) | Phase 1 | 6 |
| DSP (Dispatcher + Greenhouse) | Phase 2 | 10 |
| DET (Detection) | Phase 3 | 7 |
| PRV (Provider modules + filtering) | Phase 4 | 9 |
| DDP (Dedup, scoring, enrichment) | Phase 5 | 8 |
| OUT (Output, cleanup, close) | Phase 6 | 7 |
| STR (Stretch P1) | Phases 3 + 4 | 4 |
| CON (Concerns cleanup) | Phases 1 + 3 + 5 + 6 | 21 |

**Per-phase totals (with CON cleanup folded in):**

| Phase | Total reqs |
|-------|-----------|
| 1 | 13 (SCH×6 + CON×7) |
| 2 | 10 (DSP×10) |
| 3 | 10 (DET×7 + STR×2 + CON×1) |
| 4 | 11 (PRV×9 + STR×2) |
| 5 | 16 (DDP×8 + CON×8) |
| 6 | 12 (OUT×7 + CON×5) |

STR placement rationale:
- **STR-01** (JSON-LD fallback) → Phase 4: it's effectively a sixth provider, normalized through the same `Listing`, lands alongside Lever/Ashby/SmartRecruiters/Workday.
- **STR-02** (slug confidence + manual lock) → Phase 3: written by the detection code path; honored by `/scout-detect` from day one.
- **STR-03** (per-provider posted-date override) → Phase 4: rides on the filtering layer that lands with the remaining providers.
- **STR-04** (idempotent `/scout-detect`) → Phase 3: behavior of the detection skill itself.

CON placement rationale (surgical, no dedicated cleanup phase):
- **Phase 1** absorbs items in `scripts/` and validate-data/state/templates that are already being touched for the v=4 schema migration: CON-01 (consolidate KeyError), CON-02 (status enum), CON-03 (mine_connections header), CON-04 (`--break-system-packages` → pipx), CON-05 (`LEGACY_DATA_DIRS`), CON-06 (`companies_per_day` drift), CON-07 (state.json file perms).
- **Phase 3** absorbs the dead `commands/scout-run.md` doc references (CON-08) since the same skill-doc files are being edited for the new `/scout-detect` skill.
- **Phase 5** absorbs items in `scoring-rubric.md`, `scout-run/SKILL.md`, and `tracker_utils.py` that are already being modified for dedup/tier/enrich: CON-09/10 (dead `pipeline_tier` refs), CON-11 (LinkedIn rate-limit), CON-12 (JD lazy-load resilience), CON-13 (`extract_job_id` split), CON-14 (`skipped_stale` rename), CON-15 (Pass-2 board-broken warnings), CON-20 (`_write_tracker` user-column preservation).
- **Phase 6** absorbs cross-cutting close-out items on the same files being touched for v0.4.0 release: CON-16 (version sprawl in lockstep), CON-17 (inline column list deletion), CON-18 (PII warning), CON-19 (.gitignore + resume_path warning), CON-21 (post-write validation check).

## Out of Scope (v0.4)

Per `REQUIREMENTS.md`, the following are deferred and **not in this roadmap**:
- Jobvite/Taleo/iCIMS/Workable provider modules (v0.5+)
- `/scout-stats` reader skill (v0.4.x or v0.5+)
- Canonical-URL dedup via redirect resolution (v0.5+)
- Cross-run cross-source dedup (v0.5+)
- ETag / If-Modified-Since caching (v0.5+)
- Adaptive per-provider rate limiting (v0.5+)
- Tracker xlsx incremental writes (v0.5+)
- Workday tenant CSRF/session-token harvesting (v0.5+)
- `/scout-run --quiet` and `--only-pass=` / `--only-companies=` flags (v0.5+)
- Field-completion telemetry surfaced in summary block (lives in `runs.jsonl` only for v0.4)

---
*Roadmap created: 2026-04-27*
*Granularity: standard (6 phases, derived from REQUIREMENTS categories + research SUMMARY.md recommendation)*

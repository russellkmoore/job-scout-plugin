---
phase: 3
slug: detection-scout-detect-skill-lazy-inline-detect-dead-doc-ref-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-28
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | none (invoke directly via venv python) |
| **Quick run command** | `~/.job-scout-venv/bin/python3 -m pytest tests/test_detection.py --tb=short -q` |
| **Full suite command** | `~/.job-scout-venv/bin/python3 -m pytest tests/ --tb=short -q` |
| **Estimated runtime** | ~3 seconds (no network — fixture-driven) |

---

## Sampling Rate

- **After every task commit:** Run `~/.job-scout-venv/bin/python3 -m pytest tests/test_detection.py --tb=short -q`
- **After every plan wave:** Run full suite (`tests/`)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| DET-01 | Two-factor gate (200 + ≥1 job + name fuzzy ≥85%) → CONFIRMED; both factors required | unit | `pytest tests/test_detection.py::test_two_factor_gate -x` | ❌ W0 |
| DET-02 | `Provider.detect()` reused per-provider; iteration stops at first CONFIRMED | unit | `pytest tests/test_detection.py::test_provider_iteration -x` | ❌ W0 |
| DET-03 | `/scout-detect` skill: batch over top-30 from master_targets.csv; idempotent (skip rows ≤30d) | smoke + unit | `grep "^name: scout-detect" skills/scout-detect/SKILL.md` + `pytest tests/test_detection.py::test_idempotency -x` | ❌ W0 |
| DET-04 | Lazy inline detect in `/scout-run` Step 2b; missing `ats_provider` triggers detect; sentinel = `none` on miss | unit | `pytest tests/test_detection.py::test_lazy_inline_sentinel -x` | ❌ W0 |
| DET-05 | Confidence tiers: ≥95% high (auto-accept), 70–95% medium (BORDERLINE → review CSV), <70% NOT_FOUND | unit | `pytest tests/test_detection.py::test_confidence_tiers -x` | ❌ W0 |
| DET-06 | Detection results persist via tracker write boundary (4 cols populated) | unit | `pytest tests/test_detection.py::test_persist_columns -x` | ❌ W0 |
| DET-07 | Detection telemetry → runs.jsonl append-only, one line per company-provider attempt | unit | `pytest tests/test_detection.py::test_detection_telemetry -x` | ❌ W0 |
| STR-02 | `/scout-detect/SKILL.md` follows skill-format conventions (frontmatter, allowed-tools, references, steps) | smoke (grep) | Frontmatter regex + allowed-tools section present | ❌ W0 |
| STR-04 | `scripts/ats/detect.py` follows sibling-script bootstrap + CLI subcommand dispatch (`detect-one`, `detect-batch`) | smoke + unit | `grep "SCRIPTS_DIR" scripts/ats/detect.py` + `pytest tests/test_detection.py::test_cli_dispatch -x` | ❌ W0 |
| CON-08 | No dead refs to deleted Chrome scraping commands (`commands/scout-run.md`) in skills/ | grep gate | `grep -rn "commands/scout-run.md" skills/` → 0 matches | n/a |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `~/.job-scout-venv/bin/pip install rapidfuzz` — new dependency for fuzzy name match (NOT yet installed)
- [ ] `tests/test_detection.py` — stubs covering DET-01..07, STR-02, STR-04
- [ ] `tests/conftest.py` (extend if needed) — shared `httpx.Client` mock fixture using existing `tests/fixtures/ats/greenhouse/airbnb.json`
- [ ] `skills/scout-detect/SKILL.md` — new skill file (frontmatter + steps)
- [ ] `scripts/ats/detect.py` — new module (CLI dispatch + detect-one + detect-batch)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `/scout-detect` invocation against real master_targets.csv top-30 | DET-03 acceptance | Requires real network + actual user data | After execute-phase: `/scout-detect`, then inspect `master_targets.csv` for populated `ats_provider` columns and `runs.jsonl` for telemetry lines |
| Lazy inline detect during `/scout-run` produces `ats_provider=none` for unmappable companies | DET-04 acceptance | Requires running full /scout-run with a previously-unmapped company | Add a synthetic test company to master_targets.csv with empty ats_provider, run `/scout-run`, confirm `ats_provider` column updates |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers `pip install rapidfuzz`, `tests/test_detection.py`, fixture infra
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner approves Wave 0 task structure)

**Approval:** pending

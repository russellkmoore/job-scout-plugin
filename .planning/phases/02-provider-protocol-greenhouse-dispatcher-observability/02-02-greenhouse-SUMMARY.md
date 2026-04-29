---
phase: 02-provider-protocol-greenhouse-dispatcher-observability
plan: 02
subsystem: ats
tags: [greenhouse, provider-protocol, fixture, html-stripping, duck-typing]

# Dependency graph
requires:
  - phase: 02-provider-protocol-greenhouse-dispatcher-observability
    provides: Provider Protocol contract (base.py); Listing dataclass + REQUIRED_FIELDS (normalize.py); FetchOutcome + aggregate_outcomes + fetch_all (dispatcher.py); RunOutcome + append_run (runs_log.py); empty PROVIDERS registry (__init__.py)
provides:
  - "scripts/ats/providers/greenhouse.py — first conformant Provider Protocol implementation (Greenhouse public Job Board API)"
  - "PROVIDERS['greenhouse'] registered as the greenhouse module — duck-typed Protocol conformance"
  - "tests/fixtures/ats/greenhouse/airbnb.json — sanitized 3-job slice from boards-api.greenhouse.io/v1/boards/airbnb/jobs?content=true (provenance documented in SOURCE.md)"
  - "HTML-entity-aware description stripping (html.unescape + HTMLParser two-stage pipeline) — Greenhouse `content` is double-encoded HTML"
  - "Per-job ValueError swallow + WARNING-to-stderr inside greenhouse.fetch (one bad job doesn't nuke the whole fetch)"
affects:
  - "Plan 02-03 — wires PROVIDERS into /scout-run Step 2.5 via fetch_all([(slug, 'greenhouse')], cfg); greenhouse fetch already returns FetchResult with raw[] for ats_raw/<provider>/<slug>.json persistence"
  - "Phase 3 detection — greenhouse.detect() returns BORDERLINE on 200+jobs (rapidfuzz layer not yet wired); Phase 3 layers the name fuzzy-match for full CONFIRMED status"
  - "Phase 4 remaining providers — lever/ashby/smartrecruiters/workday follow this exact module-level Protocol-conforming shape (NAME, BOARD_URL_PATTERNS, detect, board_url_from_url, fetch, to_listing)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level (not class-level) Protocol conformance — greenhouse module exposes NAME, BOARD_URL_PATTERNS, detect, board_url_from_url, fetch, to_listing as top-level attrs/functions; runtime_checkable Protocol with duck-typed module conformance"
    - "Two-stage HTML stripping: html.unescape(content) FIRST so entity-encoded tags become real tags, then HTMLParser drops the tags themselves; regex fallback on malformed HTML"
    - "3-level sibling-script bootstrap (file → providers → ats → scripts) — documented in scripts/ats/__init__.py docstring so future provider authors don't have to count dirname() calls"
    - "Conditional httpx import — provider modules don't fail at import time if httpx is missing (so to_listing can still be exercised against fixture without httpx); only fetch() raises RuntimeError"
    - "Checked-in fixture + provenance log convention — tests/fixtures/ats/<provider>/{<slug>.json, SOURCE.md} with re-capture command + sanitization log table; Phase 4 reuses this layout"

key-files:
  created:
    - "scripts/ats/providers/greenhouse.py — first Provider Protocol conformer (Greenhouse public Job Board API); NAME, BOARD_URL_PATTERNS, detect, board_url_from_url, fetch, to_listing"
    - "tests/fixtures/ats/__init__.py — empty package marker"
    - "tests/fixtures/ats/greenhouse/__init__.py — empty package marker"
    - "tests/fixtures/ats/greenhouse/airbnb.json — sanitized 3-job slice from boards-api.greenhouse.io/v1/boards/airbnb/jobs?content=true (224 jobs total at capture)"
    - "tests/fixtures/ats/greenhouse/SOURCE.md — fixture provenance + re-capture instructions + sanitization log table"
  modified:
    - "scripts/ats/__init__.py — PROVIDERS registry now contains 'greenhouse' (relative import: from .providers import greenhouse as _greenhouse_module)"

key-decisions:
  - "Greenhouse `content` is HTML-ENTITY-ENCODED HTML (`&lt;p&gt;...` not `<p>...`). _strip_html does html.unescape FIRST, then HTMLParser. Without unescape, literal `&lt;p&gt;` would remain in Listing.description and the no-`<`-or-`>` smoke assertion would not detect the bug (because there are no real `<`/`>` chars in the encoded form). [Rule 1 - Bug auto-fix vs. plan task action]"
  - "Module (not class) registration — PROVIDERS['greenhouse'] = _greenhouse_module (the imported module), so dispatcher does `PROVIDERS['greenhouse'].fetch(slug, client, sem)` and resolves to the module-level function. Matches Plan 02-01's hand-off note."
  - "Fixture slice = 3 jobs (full response was 224 jobs at capture). Three is plenty for canonical Listing shape exercise; full response would bloat the repo."
  - "Sanitization decision: `metadata` array kept intact (contains only public-facing labels like 'Workplace Type', 'Is this job part of ACC?'); `internal_job_id` kept (it's a numeric Greenhouse-internal ID with no PII); `data_compliance` kept (GDPR boilerplate). Documented as 'no redactions required' in SOURCE.md."
  - "Greenhouse.fetch's per-job try/except swallows ValueError + logs WARNING to stderr (so one malformed job doesn't nuke the whole fetch). The dispatcher's _execute_one bucketing as ERROR therefore only fires on transport failures, 4xx/5xx other than 404, JSONDecodeError, or non-greenhouse providers (where ValueError propagation isn't swallowed). SC-4's broken-fixture test wraps a stub provider WITHOUT this swallow to prove the propagation path still works for cases where a provider chooses not to swallow."
  - "404 handling: greenhouse.fetch returns FetchResult(http_status=404, listings=[], raw=[]) on 404 (no exception). This buckets as OK_ZERO at the dispatcher boundary (200 + 0 listings shape). Plan task action documented this as 'caller buckets as ERROR' but actual behavior is OK_ZERO — both interpretations are valid; OK_ZERO is consistent with how Lever 404 will behave in Phase 4 (Lever 404 = not a customer, not an error)."

requirements-completed: [DSP-09]

# Metrics
duration: 4min 33sec
completed: 2026-04-29
---

# Phase 2 Plan 02: Greenhouse Provider Summary

**First conformant Provider Protocol implementation landed: Greenhouse public Job Board API mapped to canonical Listing via module-level NAME/BOARD_URL_PATTERNS/detect/board_url_from_url/fetch/to_listing surface; PROVIDERS['greenhouse'] registered; checked-in 3-job airbnb fixture + provenance log proves end-to-end roundtrip; SC-4 broken-fixture stress test proves schema-drift surfaces as per-(company, provider) ERROR in runs.jsonl.**

## Performance

- **Duration:** ~4 min 33 sec (plan start 2026-04-29T01:27:55Z; final task verify 2026-04-29T01:32:28Z)
- **Started:** 2026-04-29T01:27:55Z
- **Completed:** 2026-04-29
- **Tasks:** 4 of 4 complete
- **Files created:** 5 (scripts/ats/providers/greenhouse.py + 4 fixture files)
- **Files modified:** 1 (scripts/ats/__init__.py — PROVIDERS registry)
- **Lines added:** 634 (270 fixture + 348 greenhouse.py + 16 __init__.py registry update)

## Accomplishments

- **First conformant Provider validates the entire Phase 2 substrate.** The Listing shape, Protocol contract, FetchResult shape, FetchOutcome bucketing, and dispatcher.aggregate_outcomes integration all worked on the first run — proving Plan 02-01's substrate decisions held up against real-world data (Airbnb's 224-job production response).
- **HTML-entity-encoding edge case caught at fixture-capture time.** Live-captured Greenhouse responses showed that `content` is HTML-ENTITY-encoded (not raw HTML), which a naive HTMLParser-only stripper would miss. The two-stage `html.unescape() + HTMLParser` pipeline handles this correctly and the smoke assertion (`'<' not in description`) catches regressions.
- **SC-4 ERROR-bucketing proven without modifying greenhouse.py.** The stress test stubs a `_BrokenGreenhouse` class that bypasses greenhouse.fetch's per-job try/except and lets the ValueError propagate to `_execute_one` — proving the dispatcher's worker wrapper catches schema drift even when a provider chooses not to swallow internally. The broken fixture file is cleaned up after the test (not committed).
- **Live-network capture documented for re-capture.** SOURCE.md preserves the exact curl command, date, slice rationale, and sanitization-log table so future contributors can re-capture without scavenger-hunting.
- **Anti-features honored.** Zero `import asyncio`, zero `import rapidfuzz`, zero `--break-system-packages`, zero modifications to skills/scout-run/SKILL.md (Plan 02-03 owns that file). User's pending uncommitted edits in plugin.json + scout-run/SKILL.md preserved untouched throughout execution.

## Task Commits

Each task was committed atomically:

1. **Task 1: Capture sanitized Greenhouse fixture + provenance log** — `1c9d270` (test) — 4 files, 270 lines.
2. **Task 2: Write scripts/ats/providers/greenhouse.py** — `f358454` (feat) — 1 file, 348 lines.
3. **Task 3: Register greenhouse in PROVIDERS** — `31d3762` (feat) — 1 file, 16 lines.
4. **Task 4: SC-4 broken-fixture ERROR-bucket roundtrip** — *no commit* (acceptance gate; broken fixture deleted post-test, no source files changed).

**Plan metadata commit:** `<this commit>` (docs: plan summary + state + roadmap update)

## Files Created/Modified

- **`scripts/ats/providers/greenhouse.py` (348 lines)** — Module-level Provider Protocol surface: `NAME = "greenhouse"`, `BOARD_URL_PATTERNS` (3 regex patterns: boards.greenhouse.io, boards-api.greenhouse.io, job-boards.greenhouse.io), `LIST_URL_TEMPLATE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"`, `_HTMLStripper` (HTMLParser subclass), `_strip_html` (html.unescape + HTMLParser two-stage), `board_url_from_url(url)`, `detect(slug, name, client) -> DetectionResult` (returns NOT_FOUND on 404, BORDERLINE on 200+jobs awaiting Phase 3 fuzzy match, ERROR otherwise), `fetch(slug, client, semaphore) -> FetchResult` (404 → empty FetchResult; non-200 → raise; per-job ValueError → WARNING + skip), `to_listing(payload) -> Listing` (maps Greenhouse-shaped dict to canonical Listing; raises ValueError on missing required field via Listing.__post_init__).

- **`scripts/ats/__init__.py` (modified, +16/-4 lines)** — Replaced empty `PROVIDERS: Dict[str, "Provider"] = {}` with relative import (`from .providers import greenhouse as _greenhouse_module`) + `PROVIDERS = {_greenhouse_module.NAME: _greenhouse_module}`. Registers the MODULE (not an instance/class) so dispatcher's duck-typed Protocol conformance via `PROVIDERS["greenhouse"].fetch(slug, client, sem)` resolves to the module-level function.

- **`tests/fixtures/ats/__init__.py` (1 line)** — Package marker.
- **`tests/fixtures/ats/greenhouse/__init__.py` (1 line)** — Package marker.
- **`tests/fixtures/ats/greenhouse/airbnb.json` (~26 KB)** — Sanitized 3-job slice from `boards-api.greenhouse.io/v1/boards/airbnb/jobs?content=true` (224 jobs total at capture). Each job has all 15 keys greenhouse.py reads (id, title, absolute_url, first_published, location.name, content, departments[].name, metadata, company_name) plus 6 additional keys (data_compliance, internal_job_id, language, offices, requisition_id, updated_at) kept for fixture realism.
- **`tests/fixtures/ats/greenhouse/SOURCE.md` (~2.5 KB)** — Provenance + re-capture command + sanitization-log table. Documents that the airbnb response is fully public-facing and no fields required redaction.

## Decisions Made

- **HTML entity decode FIRST, then HTMLParser** (Rule 1 auto-fix vs. plan task action — see Deviations section).
- **Module-level registration in PROVIDERS** matches Plan 02-01's hand-off note. The class-vs-instance-vs-module choice was implicitly resolved by Plan 02-01's `runtime_checkable Protocol` design and the substrate's existing module-only test (`hasattr(gh, m) for m in (...)`).
- **Fixture slice = 3 jobs.** Plan task action specified 3; full response (224) would bloat the repo without adding signal. The slice covers diverse shapes (FTC role, full-time, internship; Hybrid/Remote workplace types; multiple locations) — sufficient for canonical Listing exercise.
- **Sanitization: no redactions.** Greenhouse public Job Board API contains only public-facing fields; the `metadata` array is freeform user-defined labels with no PII. Documented as such in SOURCE.md so future re-captures know the convention.
- **404 in greenhouse.fetch returns FetchResult (not raise).** Plan task action documented "caller buckets as ERROR" but actual code returns FetchResult(http_status=404, listings=[]) which buckets as OK_ZERO. Both interpretations are valid; OK_ZERO is more consistent with Phase 4's Lever 404 (not a customer). The 404 path is exercised in Phase 3 detection, not Phase 2 — so this is a Phase 2 "no observable difference" choice.
- **Followed plan elsewhere as written.** Sibling-bootstrap shape, conditional httpx import, BOARD_URL_PATTERNS regex, detect's BORDERLINE-vs-CONFIRMED Phase 2-vs-3 split, fetch's per-job try/except shape, to_listing's required vs. optional field split, employment_type metadata-array probe, PROVIDERS registration shape — all match the plan's locked decisions verbatim.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] HTML-entity-encoded `content` not stripped by HTMLParser-only pipeline**

- **Found during:** Task 2 implementation (inspection of fixture content field before writing greenhouse.py).
- **Issue:** Plan task action's `_strip_html` fed `content` directly to HTMLParser, but Greenhouse's `content` field is HTML-ENTITY-ENCODED HTML — `&lt;p&gt;...&lt;/p&gt;`, not `<p>...</p>`. HTMLParser only emits `handle_data` for text between REAL tags; with no real `<` or `>` characters in entity-encoded input, every entity-encoded tag would be treated as literal text and end up in Listing.description. Worse: the smoke assertion `'<' not in description` would PASS (because there are no real `<` chars in the encoded form), masking the bug end-to-end.
- **Fix:** Two-stage pipeline in `_strip_html`: `html.unescape(content)` FIRST so entity-encoded tags become real tags, then `HTMLParser.feed()` drops the tags themselves. Added 4-line docstring explaining the why. Added `import html` to module imports.
- **Files modified:** `scripts/ats/providers/greenhouse.py` (`_strip_html` body + docstring + import).
- **Verification:** Task 2 verify ran the smoke assertion against the live fixture — all 3 description fields stripped correctly with no `<` or `>` characters; smoke confirmed via `Task 2 OK: 3 listings parsed from fixture`.
- **Committed in:** `f358454` (rolled into the same Task 2 commit; the fix was applied while writing the file the first time).

---

**Total deviations:** 1 auto-fixed ([Rule 1 - Bug])
**Impact on plan:** Single auto-fix preserved the locked HTML-stripping behavior promise (description has no markup) against a real Greenhouse response shape that the plan task action would have silently failed against. Net effect: greenhouse.py works correctly against real production responses, not just hand-written fixtures.

## Issues Encountered

- **None outside the one Rule-1 auto-fix above.** All four task verify gates passed on the first try after the auto-fix; SC-4 broken-fixture roundtrip succeeded; plan-level smoke (`PHASE-2 PLAN-02 SMOKE: end-to-end greenhouse roundtrip OK`) succeeded; cleanup of the broken fixture confirmed (`Task 4 final: broken fixture cleanly removed`).

## Authentication Gates

None encountered. Greenhouse public Job Board API is unauthenticated; no auth gate involved.

## User Setup Required

None. The fixture is checked in; greenhouse.py imports the existing httpx (already installed in `~/.job-scout-venv` by Plan 02-01 Task 0). Plan 02-03 will wire `[ATS-PREVIEW]` into /scout-run; users won't see the new code path until that lands.

## Verify Results

All four task verify gates plus the plan-level smoke:

```
Task 1 OK: 3 jobs in fixture
Task 1 VERIFY: PASS

Task 2 OK: 3 listings parsed from fixture
Task 2 OK: ValueError raised on empty required field

Task 3 OK: PROVIDERS[greenhouse] registered + dispatcher.aggregate_outcomes integration verified

Task 4 OK: SC-4 broken-fixture ERROR-bucket roundtrip verified
Task 4 OK: cleanup of broken fixture complete
Task 4 final: broken fixture cleanly removed; SC-4 acceptance gate passed

PHASE-2 PLAN-02 SMOKE: end-to-end greenhouse roundtrip OK
```

Compliance gates:

- `import asyncio` count in `scripts/ats/providers/greenhouse.py`: **0** (anti-feature honored)
- `import rapidfuzz` count in `scripts/ats/providers/greenhouse.py`: **0** (rapidfuzz is Phase 5 dedup; greenhouse.detect returns BORDERLINE awaiting Phase 3's fuzzy-match layer)
- `break-system-packages` count in `scripts/ats/providers/greenhouse.py`: **0** (CON-04 honored — pipx/venv install hint pattern)
- `skills/scout-run/SKILL.md` modified count in plan commits: **0** (Plan 02-03 owns that file; user's pending uncommitted edits preserved)
- `tests/fixtures/ats/greenhouse/_broken_no_title.json` exists in working tree: **No** (cleaned up by Task 4 post-test)
- `git status --short` after final task: matches initial state (only `M .claude-plugin/plugin.json` + `M skills/scout-run/SKILL.md` — user's pending edits, untouched)

## Hand-off to Plan 02-03 ([ATS-PREVIEW] wire-in to /scout-run)

The Greenhouse provider is ready to be invoked from /scout-run Step 2.5. Plan 02-03 will:

```python
# Plan 02-03 will write code shaped like this in /scout-run Step 2.5:
from ats.dispatcher import fetch_all, aggregate_outcomes
from ats.runs_log import append_run

targets = [(slug, "greenhouse") for slug in greenhouse_slugs_from_master_targets]
outcomes = fetch_all(targets, config_path)
per_p, per_cp, per_pl = aggregate_outcomes(outcomes)
append_run(runs_log_path, wall_clock, per_p, per_cp, per_pl)

# For each OK_WITH_RESULTS outcome, persist raw[] to ats_raw/greenhouse/<slug>.json
for o in outcomes:
    if o.outcome == RunOutcome.OK_WITH_RESULTS and o.raw:
        path = f"{daily_dir}/ats_raw/{o.provider}/{o.company_slug}.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(o.raw, f, indent=2)
```

**Verification surface for Plan 02-03 SC-1, SC-2, SC-3:**

- SC-1 (listings appear in report): `outcomes[i].listings` is a `List[Listing]`; each Listing has `source = "ats:greenhouse"` and the report renderer (Phase 6) reads that.
- SC-2 (runs.jsonl auditable): The 3-key dict from `aggregate_outcomes` is exactly what `append_run` consumes; per-(company, provider) hit counts + field_completion telemetry already write correctly (verified in this plan's smoke).
- SC-3 (kill-switch): No code change needed in greenhouse.py; the dispatcher's `ats.concurrency_disabled` path runs `_execute_one` sequentially against the same provider — already exercised in Plan 02-01.
- SC-4 (broken fixture surfaces as ERROR): Verified end-to-end in this plan's Task 4. greenhouse.fetch's per-job try/except prevents one bad job from nuking a fetch, but the dispatcher's worker wrapper catches any unswallowed ValueError + buckets as ERROR with the field name in the error message — proven by `_BrokenGreenhouse` stub in Task 4.

**No scavenger hunt for Plan 02-03.** The dispatcher's public API (fetch_all + aggregate_outcomes) is unchanged from Plan 02-01; greenhouse.py drops in via PROVIDERS registry; the runs.jsonl line shape is identical to Plan 02-01's empty-roundtrip smoke. Plan 02-03 only writes the wire-in code in /scout-run Step 2.5 + the ats_raw/<provider>/<slug>.json persistence loop.

## Self-Check: PASSED

- All 5 created files exist on disk: `scripts/ats/providers/greenhouse.py`, `tests/fixtures/ats/__init__.py`, `tests/fixtures/ats/greenhouse/__init__.py`, `tests/fixtures/ats/greenhouse/airbnb.json`, `tests/fixtures/ats/greenhouse/SOURCE.md` — verified via `test -f` for each.
- Modified file `scripts/ats/__init__.py` contains `from .providers import greenhouse as _greenhouse_module` and `PROVIDERS["greenhouse"]`-equivalent registration — verified via `grep`.
- All 3 task commits exist in git log:
  - `1c9d270` — test(02-02): add checked-in Greenhouse fixture (airbnb 3-job slice) + provenance log (DSP-09)
  - `f358454` — feat(02-02): add Greenhouse provider conforming to Provider Protocol (DSP-09)
  - `31d3762` — feat(02-02): register greenhouse in scripts/ats/__init__.py:PROVIDERS (DSP-09)
- All success criteria gates passed (asyncio=0, rapidfuzz=0, break-system-packages=0, skills/scout-run/SKILL.md untouched in plan commits, broken fixture cleanly removed).
- Plan-level smoke confirmed end-to-end: `PHASE-2 PLAN-02 SMOKE: end-to-end greenhouse roundtrip OK`.

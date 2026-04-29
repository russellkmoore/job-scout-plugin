# Phase 5: Cross-source Dedup + ATS Tier Bump + Enrich-then-Tier + Scoring/Tracker Cleanup — Research

**Researched:** 2026-04-28
**Domain:** Fuzzy dedup (rapidfuzz), SKILL.md flow rewrite, tracker_utils.py surgery, scoring-rubric + search-config.md doc fixes
**Confidence:** HIGH — all findings verified against current codebase (committed HEAD, branch main)

---

## Summary

Phase 5 is the most cross-cutting phase in the v0.4 milestone. It has 16 requirements spanning five distinct surfaces: a new `scripts/ats/dedupe.py` module, two skill-doc files (`scoring-rubric.md`, `search-config.md`), `skills/scout-run/SKILL.md` (flow rewrite + enrichment step), and `scripts/tracker_utils.py` (three surgical fixes). It also inherits one deferred deliverable from Phase 4: routing `ats_provider="none"` + `careers_url` companies through `jsonld.py`.

**Primary recommendation:** Split into 4 plans along natural surface boundaries: (1) Wave 0 test scaffolding + `scripts/ats/dedupe.py`, (2) `scout-run/SKILL.md` flow rewrite (JSON-LD routing + dedup invocation + enrich-then-tier + regression warnings), (3) scoring-rubric + search-config doc fixes (CON-09, CON-10), (4) `tracker_utils.py` surgery (CON-13, CON-14, CON-15, CON-20). Plans 3 and 4 are independent of each other and of Plan 2's SKILL.md changes — they can execute in parallel once Plan 1 is merged.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Two-key fuzzy dedup (DDP-01, DDP-02, DDP-03) | Script (`scripts/ats/dedupe.py`) | SKILL.md invokes it | Deterministic logic belongs in scripts, not prompts |
| ATS tier bump +1 (DDP-05) | SKILL.md scoring step (Step 5) | `scoring-rubric.md` documents it | LLM applies the rule at scoring time; rubric is the authority doc |
| Enrich-then-tier ordering (DDP-04, DDP-05) | SKILL.md Step 5 (new order: enrich → tier) | — | Pure flow rewrite in the prompt; no script needed |
| LinkedIn enrichment Chrome calls (DDP-04) | SKILL.md Step 5 | `chrome-setup.md` for JD lazy-load patterns | Chrome MCP is skill-level; only A-tier ATS candidates |
| ATS regression-suspect warnings (DDP-06, DDP-08) | SKILL.md Step 6 (Honest notes section) | reads `runs.jsonl` via Bash | Report-rendering logic; reads JSONL that was built by Phase 2 |
| Pass-2 board-broken warnings (CON-15, DDP-07) | SKILL.md Step 3 + Step 6 | same `runs.jsonl` reads | Same mechanism as DDP-06; surfaced in same Honest notes |
| JSON-LD routing for `ats_provider=none` (deferred STR-01) | SKILL.md Step 2.5 + `preview.py` | `jsonld.py` already exists | SKILL.md and preview.py already support the hook; just need the filter |
| `extract_job_id` split (CON-13) | `scripts/tracker_utils.py` | all 4 callers in same file | Surgical rename + caller migration; no other modules involved |
| `skipped_stale` rename (CON-14) | `scripts/tracker_utils.py` | — | One local variable + one comment; self-contained |
| User-column preservation (CON-20) | `scripts/tracker_utils.py:_write_tracker` + `load_tracker` | — | Both read and write paths need surgery; openpyxl API |
| Dead `pipeline_tier` refs (CON-09, CON-10) | `search-config.md` + `scoring-rubric.md` | — | Markdown doc edits only; no Python changes |
| LinkedIn rate-limit/backoff (CON-11) | SKILL.md Step 5 (enrichment) | `chrome-setup.md` (optional) | Behavioral rule added to skill prompt |
| LinkedIn JD lazy-load resilience (CON-12) | SKILL.md Step 5 + `chrome-setup.md` | `runs.jsonl` for telemetry | Multiple selectors + retry; telemetry via existing runs.jsonl append |

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DDP-01 | `scripts/ats/dedupe.py` matches Pass 2 (LinkedIn) listings against Pass 1 (ATS) via `rapidfuzz.token_set_ratio` on normalized titles, scoped per company slug | See Dedup Architecture section; rapidfuzz already installed in `~/.job-scout-venv` |
| DDP-02 | Tiered confidence band: ≥95% auto-merge, 70–94% log to review, <70% keep both; thresholds in `config.json` under `dedup.thresholds` | See Dedup Architecture; `ats_detection_review.csv` path established in Phase 3 |
| DDP-03 | Two-key match: auto-merge requires BOTH loose (slug + first-3-tokens) AND tight (slug + full normalized title) to agree at ≥95%; either alone = review band | See Two-Key Gate section |
| DDP-04 | `runs.jsonl` line carries `dedup_decisions` array with both source listings and score | `append_run()` in `runs_log.py` accepts any kwargs; add `dedup_decisions` to the line dict |
| DDP-05 | `scoring-rubric.md` +1 tier bump for `source=ats:*` listings ≤30d old; ATS postings >30d get no bump | Dead `pipeline_tier +5` row (CON-10) is replaced by this; coordinate with CON-10 |
| DDP-06 | SKILL.md Step 5 enrichment: for every A-tier `source=ats:*` listing, Chrome MCP → LinkedIn company page → capture shared-connection count + top 3 named connections | See Enrich-then-Tier section |
| DDP-07 | Chrome MCP limited to LinkedIn navigation only; every `mcp__Claude_in_Chrome__navigate` against marketing/careers domains removed | SKILL.md Step 2 still has career-page navigation calls — those get removed (Phase 6 fully deletes them; Phase 5 scopes them out of enrichment) |
| DDP-08 | Report Honest notes auto-flags "ATS regression suspect": `(provider, company)` returned OK_WITH_RESULTS ≥3 of last 5 runs but OK_ZERO/ERROR today | Reads `runs.jsonl` `per_company_provider` field; same mechanism as CON-15 |
| CON-09 | Rewrite `search-config.md:52` dead `pipeline_tier <= 2` Pass 1 priority to use `linkedin_connection_count` thresholds | Text edit; See CON-09/10 section |
| CON-10 | Rewrite `scoring-rubric.md:111` dead `pipeline_tier 1-3 +5` bonus to ATS-warm-path +1 rule (coordinate with DDP-05) | Text edit; the +5 bonus row becomes the DDP-05 ATS tier-bump row |
| CON-11 | Add rate-limit/backoff rule to SKILL.md enrichment step: pause 10–15s between every 5th LinkedIn navigation | One sentence added to Step 5; see CON-11 section |
| CON-12 | LinkedIn JD lazy-load resilience: try multiple selectors, retry once with longer wait if <500 chars, log failures to `runs.jsonl` | See CON-12 section; `chrome-setup.md` also updated |
| CON-13 | Split `extract_job_id` → `extract_linkedin_job_id` (LinkedIn-anchored regex) + `extract_dedup_key` (URL-as-string fallback); migrate all 4 callers | See CON-13 section; all callers are in `tracker_utils.py` |
| CON-14 | Rename `skipped_stale` → `flagged_stale_count` in `tracker_utils.py:194-199`; remove misleading comment | One-line rename; see CON-14 section |
| CON-15 | Add Pass-2 board-broken warnings to SKILL.md Step 3 + Step 6: if a board returned 0 results ≥3 of last 5 runs (per `runs.jsonl`), surface "board appears broken" in Honest notes | Same `runs.jsonl` read mechanism as DDP-08; Step 3 adds the check, Step 6 renders it |
| CON-20 | Modify `_write_tracker` to preserve user-added xlsx columns on append: capture extra columns in `load_tracker`, re-emit them in `_write_tracker` | See CON-20 section; openpyxl passthrough buffer pattern |
</phase_requirements>

---

## Standard Stack

All dependencies already installed in `~/.job-scout-venv`. No new packages needed. [VERIFIED: grep of dispatcher.py, Phase 4 install record]

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| `rapidfuzz` | installed (Phase 3) | `token_set_ratio` for title fuzzy match | Already used by `detect.py` |
| `openpyxl` | installed | xlsx read/write for CON-20 | Already used by `tracker_utils.py` |
| `re`, `json`, `csv`, `datetime` | stdlib | Normalization, JSONL reads, dedup CSV | Already in use throughout |

---

## Architecture Patterns

### System Architecture Diagram

```
/scout-run SKILL.md Step 2.5 (existing)
    → preview.py → fetch_all → [6 providers incl. jsonld (NEW: careers_url routing)]
    → outcomes → apply_filters → raw JSON persisted
    → runs.jsonl line appended
         ↓
Pass 2 LinkedIn listings (existing Step 3/4)
         ↓
SKILL.md Step 4.5 (NEW): Invoke scripts/ats/dedupe.py
    Input: Pass 1 Listing dicts (from ats_raw/) + Pass 2 candidate set
    Output: merged_set + review_band + runs.jsonl dedup_decisions
         ↓
SKILL.md Step 5 (REWRITTEN): Enrich-then-Score
    For every A-tier candidate where source=ats:*:
        Chrome MCP → LinkedIn company page → connection count + names
        [rate-limit: pause 10–15s every 5 navigations]
        [JD resilience: try 3 selectors, retry once if <500 chars]
    Apply scoring rubric (+1 ATS bump for ≤30d postings)
    Assign tier after enrichment data is in hand
         ↓
SKILL.md Step 6: Build report
    Honest notes: ATS regression suspects (from runs.jsonl)
                  Pass-2 board-broken warnings (from runs.jsonl)
         ↓
SKILL.md Step 7: tracker_utils.py append (CON-20: user columns preserved)
```

### Recommended Project Structure (Phase 5 additions)

```
scripts/ats/
├── dedupe.py           # NEW — DDP-01/02/03/04; two-key tiered fuzzy dedup
skills/scout-run/
└── SKILL.md            # REWRITTEN — Step 2.5 (JSON-LD routing), Step 4.5 (dedup), Step 5 (enrich-then-tier)
skills/job-scout/references/
├── scoring-rubric.md   # EDITED — CON-10 + DDP-05 (+1 ATS bump row)
└── search-config.md    # EDITED — CON-09 (pipeline_tier → connection_count priority)
scripts/
└── tracker_utils.py    # EDITED — CON-13, CON-14, CON-20
skills/job-scout/references/
└── chrome-setup.md     # EDITED — CON-12 (resilient JD lazy-load selectors)
```

---

## Dedup Architecture (DDP-01, DDP-02, DDP-03, DDP-04)

### Where the hook lives

**New script: `scripts/ats/dedupe.py`** — called from SKILL.md as a new Step 4.5 between Pass 2 completion and scoring (Step 5). The SKILL invokes it with ONE Bash call:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/dedupe.py \
  cross-source \
  "<data_dir>/daily/<TODAY>/ats_raw/" \
  "<data_dir>/daily/<TODAY>/linkedin_candidates.json" \
  "<data_dir>/daily/<TODAY>/dedup_result.json" \
  --config "<data_dir>/config.json"
```

Outputs `dedup_result.json`:
```json
{
  "merged": [...],
  "review_band": [...],
  "linkedin_only": [...],
  "ats_only": [...],
  "decisions": [
    {"action": "auto_merge", "ats_url": "...", "linkedin_url": "...", "loose_score": 97, "tight_score": 96, "company_slug": "stripe"},
    {"action": "review_band", "ats_url": "...", "linkedin_url": "...", "loose_score": 88, "tight_score": 72, "company_slug": "lululemon"},
    {"action": "keep_both", "ats_url": "...", "linkedin_url": "...", "loose_score": 65, "tight_score": 60, "company_slug": "acme"}
  ]
}
```

The SKILL reads `dedup_result.json` and appends `decisions` to the `runs.jsonl` line via a `runs_log.append_run` call that includes `dedup_decisions`. [ASSUMED — `append_run()` accepts `**kwargs` so the schema can be extended; verify against runs_log.py signature before coding]

Actually: [VERIFIED: `append_run()` signature in `runs_log.py` does NOT currently accept `dedup_decisions`]. The function builds the line dict internally. Plan must either (a) add a `dedup_decisions` kwarg to `append_run()`, or (b) have the SKILL Bash-call `runs_log.py append-run` with an extended stats.json that includes `dedup_decisions`. Option (b) avoids modifying runs_log.py. The CLI entry point (`if __name__ == "__main__"`) already reads a stats.json and passes it to `append_run()` — extend the stats.json schema to include an optional `dedup_decisions` key and pass it through. This is the lower-risk path.

### Two-key normalization

[VERIFIED: `normalize.py` already has `_normalize_title()` — lowercase + strip punctuation + collapse whitespace. Phase 5 re-uses this function.]

```python
def _normalize_title(title: str) -> str:
    # Already exists in normalize.py — import, don't duplicate
    t = (title or "").casefold()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def _loose_key(slug: str, title: str) -> str:
    tokens = _normalize_title(title).split()
    return slug + "|" + " ".join(tokens[:3])

def _tight_key(slug: str, title: str) -> str:
    return slug + "|" + _normalize_title(title)
```

Auto-merge condition (DDP-03): `loose_score >= threshold AND tight_score >= threshold`. Either alone = review band.

### Tiered band thresholds (DDP-02)

Configurable via `config.json` under `dedup.thresholds`. Defaults:
```json
{
  "dedup": {
    "thresholds": {
      "auto_merge": 95,
      "review_band_min": 70
    }
  }
}
```

`templates/config.json` needs these keys added in Phase 5. [ASSUMED — templates/config.json currently has an `ats` section but no `dedup` section; verify before writing]

### Merge behavior

When auto-merging (ATS wins): take ATS listing as primary. Overlay LinkedIn fields only when ATS field is empty:
- `connection_count`: prefer LinkedIn (ATS never has it)
- `salary_range`: prefer LinkedIn if stated (ATS JDs often omit comp)
- `source`: keep `ats:<provider>` (ATS is canonical)

This "take union, not winner-takes-all" pattern matches PITFALLS.md Pitfall 3 guidance. [CITED: `.planning/research/PITFALLS.md` lines 96-98]

### Edge cases

**ATS-only listing (no LinkedIn match):** Stays in `ats_only[]` → passes through to scoring with `source=ats:<provider>`. Gets +1 bump check (DDP-05).

**LinkedIn-only listing (no ATS match):** Stays in `linkedin_only[]` → passes through to scoring with `source=linkedin`. No bump.

**Partial overlap:** Same company, different roles (e.g. Stripe GH has "SWE Backend" and LinkedIn has "Software Engineer II"). Loose-key mismatch (first 3 tokens differ) → keep both. Correct behavior.

**Multi-region collapse interaction:** `collapse_regional_dupes()` in `normalize.py` already runs in Phase 4's `apply_filters()` on intra-ATS dupes BEFORE the cross-source dedup. So by the time `dedupe.py` sees Pass 1 listings, regional variants are already collapsed to a single Listing with `location="US, UK, EU"`. Cross-source dedup only sees one ATS row per role, so no interaction hazard. [VERIFIED: `apply_filters` call order in `preview.py` lines 148-149]

**JSON-LD `ats_provider=none` listings:** After Phase 5 wires the JSON-LD routing (see JSON-LD section), these listings carry `source=ats:jsonld`. They flow through `dedupe.py` on the ATS side like any other provider. The company_slug is derived from the `careers_url` domain — same slug normalization that detect.py uses.

---

## JSON-LD Invocation Routing (Deferred from Phase 4)

[VERIFIED: Phase 4 VERIFICATION.md deferred item #1, confirmed in SKILL.md Step 2.5 inline note at line 168]

### What's missing

Phase 4 shipped `jsonld.py` and registered it in PROVIDERS (6 entries confirmed). The gap is that SKILL.md Step 2.5's target-building logic silently skips `ats_provider == "none"` rows. The fix is purely in two places:

**1. SKILL.md Step 2.5 target-building block (around line 159):**

Current filter: `ats_provider in {"greenhouse", "lever", "ashby", "smartrecruiters", "workday"}`.

Add a SECOND block after this for JSON-LD candidates:
```
For any company where ats_provider == "none" AND careers_url is non-empty in master_targets.csv,
add an entry to targets_csv as: "<careers_url>|jsonld"
```

Note: `careers_url` is NOT currently in `MASTER_TARGETS_COLUMNS`. [VERIFIED: `scripts/schema.py` `MASTER_TARGETS_COLUMNS` — no `careers_url` column]. This means Phase 5 must either (a) add `careers_url` to the schema (requires `MASTER_TARGETS_VERSION` bump to 5 — **BAD**) or (b) route via a column that already exists.

**Resolution:** Check `career_page_url` (already in schema) instead of `careers_url`. The JSON-LD provider's `fetch()` accepts any URL as `slug`. For companies where `ats_provider == "none"` AND `career_page_url` is non-empty, pass `career_page_url` as the jsonld target. This avoids a schema bump and re-uses the column that Phase 3 already populates for career-page detection. `jsonld.py:fetch()` already handles any HTTP URL — it fetches, extracts `<script type="application/ld+json">JobPosting</script>` blocks, and returns listings or OK_ZERO. [VERIFIED: `jsonld.py` lines 191-240]

**2. `preview.py` target building:** No changes needed — the SKILL already passes arbitrary `slug|provider` tuples via `targets_csv`. When `<careers_url>|jsonld` arrives at `preview.py`, `run_preview()` builds `targets = [(careers_url, "jsonld")]` and `fetch_all` dispatches to `PROVIDERS["jsonld"].fetch(careers_url, client, sem)`. The existing code handles this. [VERIFIED: `preview.py` lines 228-241 — pipe-split, passes directly to targets list]

**Concurrency note:** `jsonld` needs a semaphore entry. [VERIFIED: `templates/config.json` already has `"jsonld": 2` in `provider_concurrency_caps` from Phase 4's Plan 04-05]. No change needed.

---

## Enrich-then-Tier Flow (DDP-04, DDP-05, DDP-06)

### Current SKILL.md flow (Phase 4 state)

```
Step 2   — Pass 1 company-first (legacy Chrome + ATS detection)
Step 2b  — Lazy inline detect
Step 2.5 — [ATS-PREVIEW] Pass 1 via preview.py
Step 3   — Pass 2 (other boards)
Step 4   — Pass 3 (LinkedIn keyword)
Step 5   — Score every candidate listing
Step 6   — Build report
Step 7   — Update tracker
Step 8   — Update master_targets.csv
Step 9   — Summarize to user
```

### Phase 5 target flow

```
Step 2   — [kept] Pass 1 company-first (legacy flow stays until Phase 6 deletes it)
Step 2b  — [kept] Lazy inline detect
Step 2.5 — [UPDATED] ATS Pass 1 via preview.py; now includes JSON-LD routing
Step 3   — [kept] Pass 2 other boards (add board-broken check here)
Step 4   — [kept] Pass 3 LinkedIn keyword
Step 4.5 — [NEW] Cross-source dedup: call dedupe.py; merge Pass 1 ATS + Pass 2/3
Step 5   — [REWRITTEN] Enrich-then-Tier:
             (a) For every A-tier CANDIDATE (pre-tier) where source=ats:*:
                 Chrome MCP → LinkedIn shared-connection lookup
                 [rate-limit: pause 10-15s every 5 navigations]
             (b) Apply +1 tier bump: ATS listings ≤30d old get +1 tier
             (c) Assign final tier using enriched score
Step 6   — [UPDATED] Honest notes: ATS regression suspects + Pass-2 board-broken warnings
Step 7   — [kept] Tracker append (CON-20 fixes land here)
Step 8   — [kept] master_targets.csv update
Step 9   — [kept] Summarize
```

**"A-tier CANDIDATE" definition for enrichment:** Before applying the +1 ATS bump, a listing is an "A-tier candidate" if its base score (5-category rubric, no bump) would produce tier A OR if +1 bump would push it from B to A. In other words: enrich any listing that would be A-tier after the bump is applied. This avoids enriching a listing only to discover the bump was what pushed it to A, which would require a second enrichment pass. [ASSUMED — this interpretation is not explicitly stated in REQUIREMENTS.md; the requirement says "ATS A-candidates only" which could mean (a) pre-bump A-tier or (b) post-bump A-tier. This needs user clarification — see Open Questions]

### +1 ATS tier bump mechanics (DDP-05)

The bump is a markdown rule in `scoring-rubric.md`, not a script. The SKILL reads the rubric and applies it during Step 5. The rule replaces the dead `pipeline_tier 1-3 +5` row (CON-10):

**New row in the bonus/penalty table:**
```
| ATS warm path | +1 tier | source=ats:* AND posted_date ≤ 30d ago |
```

Implementation detail: "+1 tier" means A→A (capped at A), B→A, C→B. It is NOT a score point addition — it is a tier elevation post-scoring. The rubric must be unambiguous about this. [ASSUMED — REQUIREMENTS.md says "+1 tier bump" which is most naturally a tier elevation, not a score bump. Verify with user if score-point interpretation is intended]

### LinkedIn enrichment scoping (DDP-04)

Scoped to ATS A-candidates ONLY. This matters for the 5-min wall-clock budget: each LinkedIn navigation costs 10-30s. With 5-10 A-tier ATS candidates per run, enrichment adds 50-300s. Within budget if we don't enrich B/C. [CITED: PROJECT.md "Enrich-then-tier for ATS A-candidates (LinkedIn shared-connection lookup)" + wall-clock ≤5 min constraint]

Chrome MCP call sequence (DDP-04):
1. Navigate to `https://www.linkedin.com/company/<company_slug>/people/`
2. Look for connection count + mutual connection names in page text
3. If page requires login or redirects: log `linkedin_enrich_unavailable` to runs.jsonl, continue (non-blocking)

The company_slug for LinkedIn is NOT the same as the ATS board slug. The SKILL must derive it from `master_targets.csv:company_name` (same normalization as Step 2b's detect-one slug derivation). [ASSUMED — no explicit mapping documented; user may need to confirm if `master_targets.csv` has a `linkedin_company_slug` column or if the run-time normalization is sufficient]

---

## CON-09 / CON-10: Dead `pipeline_tier` References

### CON-09 — `search-config.md:52`

[VERIFIED: `skills/job-scout/references/search-config.md` line 52 contains "Companies on the user's pipeline list (`pipeline_tier <= 2`)" in the Pass 1 priority order]

Current Pass 1 priority list (from `search-config.md` lines 50-54):
```
1. Companies with 3+ named connections (warm path likely).
2. Companies on the user's pipeline list (pipeline_tier <= 2).   ← DEAD (col removed in v3)
3. Companies in industries_preferred from config.
4. Companies with detected ATS providers (richer data).
```

Replacement:
```
1. Companies with 3+ named connections (warm path likely).
2. Companies with linkedin_connection_count ≥ 1 AND ats_provider populated (ATS + warm path).
3. Companies in industries_preferred from config.
4. Companies with any detected ATS provider (richer data).
```

Note: item 4 already exists in SKILL.md Step 2's sort logic (line 82: `linkedin_connection_count desc, last_checked asc`). The doc fix just makes it consistent with what the skill already does.

### CON-10 — `scoring-rubric.md:111`

[VERIFIED: `skills/job-scout/references/scoring-rubric.md` line 111 contains "Company on Target Pipeline | +5 | Company exists in master_targets.csv with pipeline_tier 1-3"]

Replace this row with the DDP-05 rule:
```
| ATS warm path | +1 tier | source=ats:* AND posted_date ≤ 30 days (ISO date comparison against today's date) |
```

The `pipeline_tier 1-3 +5` row is replaced entirely — it is not kept alongside the new row. The old bonus was conceptually about "pre-identified target companies"; the ATS warm-path bump serves a similar function with a defensible signal.

---

## CON-11: LinkedIn Rate-Limit/Backoff in Enrichment

[CITED: CONCERNS.md "No rate-limit / retry / backoff anywhere" — fix: "between every 5 LinkedIn navigations, pause 10–15 seconds"]

Add to SKILL.md Step 5 enrichment block:

```
Rate-limit rule (CON-11): After every 5th LinkedIn navigation in the enrichment
loop, pause 10-15 seconds before the next navigation. Count navigations across
all A-tier enrichment calls in Step 5 — the counter does not reset between
companies. If Step 5 processes 7 A-tier ATS candidates, pause after the 5th.
```

This is a behavioral instruction in the SKILL.md prompt. No script changes needed.

---

## CON-12: LinkedIn JD Lazy-Load Resilience

[CITED: CONCERNS.md lines 97-103 — "try multiple selectors for the '...more' button; if get_page_text returns <500 chars after the dance, retry once with a longer wait; log JD-extraction failures to runs.jsonl"]

The Phase 5 enrichment step uses Chrome MCP for connection lookups, NOT full JD extraction (ATS-sourced A-candidates already have `description` from `Listing.description`). However CON-12 still applies to Pass 3's LinkedIn JD extraction (Step 4) and to any LinkedIn-sourced listing that needs enrichment.

**For the chrome-setup.md update (primary selectors for "...more" button):**
1. `find: "...more"` (primary — existing)
2. `find: "Show more"` (secondary — LinkedIn A/B test variant)
3. `aria-label="Expand description"` (tertiary — accessibility attribute variant)

**Retry rule:** If `get_page_text` returns < 500 chars after the click sequence, wait an additional 3s and retry `get_page_text` once. If still < 500 chars after retry, log `jd_extraction_failed: true` to the listing's metadata and continue. The JD-failure telemetry goes into `runs.jsonl` — add a `jd_extraction_failures` count to the runs.jsonl line schema (add to `append_run`'s stats.json passthrough path, same as `dedup_decisions`).

---

## CON-13: Split `extract_job_id`

[VERIFIED: `scripts/tracker_utils.py` lines 72-77 — `extract_job_id` uses `re.search(r'(\d{10,})', str(url))` — no LinkedIn URL anchor]

### Current callers (all in `tracker_utils.py`)

| Caller | Line | Current use | Correct replacement |
|--------|------|-------------|---------------------|
| `load_tracker` | ~145 | `job_id = extract_job_id(url)` for dedup set | `extract_linkedin_job_id(url)` — stale check only valid for LinkedIn IDs |
| `append_rows` | ~196 | `job_id = extract_job_id(url)` for dedup check | `extract_linkedin_job_id(url)` — dedup by LinkedIn ID only |
| `is_stale_by_id` | ~81 | calls `extract_job_id` internally | Replace internals to call `extract_linkedin_job_id` |
| `rebuild` | ~276 | `job_id = extract_job_id(url)` for dedup | `extract_dedup_key(url)` — URL-as-string fallback for non-LinkedIn rows |

### New functions

```python
def extract_linkedin_job_id(url):
    """Extract numeric LinkedIn job ID — anchored to linkedin.com URLs only.
    Returns int or None. Returns None for non-LinkedIn URLs (career-page,
    ATS board URLs, etc.) so stale-flag and dedup skip non-LinkedIn rows.
    """
    if not url:
        return None
    match = re.search(r'linkedin\.com/jobs/(?:view|search)/\D*(\d{10,})', str(url))
    return int(match.group(1)) if match else None


def extract_dedup_key(url):
    """Return a stable dedup key for any URL. For LinkedIn URLs, returns
    the numeric job ID as a string. For other URLs, returns the URL itself
    (normalized). This key is used by rebuild() and load_tracker() to
    deduplicate non-LinkedIn rows by full URL rather than ID.
    """
    if not url:
        return None
    linkedin_id = extract_linkedin_job_id(url)
    if linkedin_id is not None:
        return str(linkedin_id)
    return str(url).strip().lower()
```

[VERIFIED: The `STALE_LINKEDIN_JOB_ID_THRESHOLD = 4_200_000_000` constant is correct and unchanged — it's only compared against LinkedIn job IDs, which `extract_linkedin_job_id` now guarantees]

**Caller migration for `append_rows` dedup check:** The dedup set (`existing_ids`) currently stores integer job IDs. After CON-13, for ATS-sourced rows the URL is an ATS board URL — `extract_linkedin_job_id` returns None, so the row is not in `existing_ids` and is always added. This is CORRECT behavior — ATS rows don't have LinkedIn IDs and should not be deduped by LinkedIn ID. Cross-run dedup for ATS rows is out of scope for v0.4 (v2 requirement DDP2-02). [CITED: REQUIREMENTS.md v2 requirements]

**For `rebuild()`:** Replace `extract_job_id` with `extract_dedup_key` — this handles both LinkedIn (returns ID string) and ATS URLs (returns normalized URL). `rebuild` deduplication then uses a string set instead of an integer set.

---

## CON-14: Rename `skipped_stale`

[VERIFIED: `scripts/tracker_utils.py` lines 188-205 — `skipped_stale` initialized at 188, incremented at 204, but the stale row is NOT skipped — it IS added to `existing_rows` with a status of "Stale — Verify". The returned dict at line 263 correctly uses `"flagged_stale": skipped_stale`]

Surgery:
1. Line 188: `skipped_stale = 0` → `flagged_stale_count = 0`
2. Line 204: `skipped_stale += 1` → `flagged_stale_count += 1`
3. Line 206 (the misleading comment): `# Still add it, but flagged — user can decide` → remove entirely
4. Line 263 (returned dict): `"flagged_stale": skipped_stale` → `"flagged_stale": flagged_stale_count`

No behavior change. Purely a rename + comment removal.

---

## CON-15: Pass-2 Board-Broken Warnings

[CITED: CONCERNS.md lines 112-115 — "every Pass 2 board should require a non-empty result on at least one of the last 3 runs, and surface a 'board appears broken' warning in the report's Honest notes section"]

### Implementation

Same mechanism as DDP-08 (ATS regression suspect). In SKILL.md Step 3, after running each Pass-2 board:

```
For each Pass-2 board (Built In Seattle, Wellfound, YC Work at a Startup, HN Algolia):
  Read the last 5 lines of <data_dir>/runs.jsonl.
  Check if this board's result count appears in per_company_provider or a "pass2_boards" block.
```

**Problem:** Current `runs.jsonl` schema only captures ATS per_company_provider outcomes. Pass-2 boards are LinkedIn/built-in scrapes — they don't go through the dispatcher and don't appear in `runs.jsonl`. The Phase 2 `append_run()` function has no slot for Pass-2 board stats.

**Resolution options:**
1. Add Pass-2 board results to `runs.jsonl` via the stats.json passthrough — add a `pass2_boards` key to the line. The SKILL reports `{"built_in_seattle": N, "wellfound": N, ...}` each run. This requires updating `append_run()` or the stats.json CLI input.
2. Use a separate lightweight file (e.g. `daily/<DATE>/pass2_stats.json`) instead of runs.jsonl. The board-broken check reads the last 3-5 such files.

Option 2 is simpler and avoids any runs.jsonl schema change. But it requires file-contract.md to be updated. [OPEN QUESTION — see Open Questions section]

---

## CON-20: User-Column Preservation in `_write_tracker`

[VERIFIED: `scripts/tracker_utils.py` lines 295-315 — `_write_tracker` iterates `enumerate(row, 1)` and breaks at `col > len(HEADERS)`. CONFIRMED that `load_tracker` at line 139-148 reads rows as lists up to `ws.max_column` — but the existing rows are padded to `len(HEADERS)` at line 141-142 only if they're SHORT. Extra-wide rows are NOT truncated in `load_tracker`... wait]

[VERIFIED more carefully: `load_tracker` line 139-142:
```python
for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
    row_list = list(row)
    if len(row_list) < len(HEADERS):
        row_list.extend([None] * (len(HEADERS) - len(row_list)))
    rows.append(row_list)
```
This pads SHORT rows but does NOT truncate LONG rows (with user-added columns). So `load_tracker` DOES read user-added column data into `rows` — but only if the user's column is beyond `len(HEADERS)` positions. The issue is in `_write_tracker` at line 323-325:
```python
for col, val in enumerate(row, 1):
    if col > len(HEADERS):
        break
```
This drops any data beyond column 16 (current `len(HEADERS)`). The read path preserves it in memory; the write path drops it.]

### Fix pattern

**In `load_tracker`:** When a row has more columns than `len(HEADERS)`, capture the extra values in a separate "passthrough" list:

```python
rows = []
user_extra_headers = []  # discovered once from header row
for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
    row_list = list(row)
    core_row = row_list[:len(HEADERS)]
    extra_row = row_list[len(HEADERS):]
    if len(core_row) < len(HEADERS):
        core_row.extend([None] * (len(HEADERS) - len(core_row)))
    rows.append(core_row + ["__EXTRA__"] + extra_row)  # sentinel-separated
```

Actually a cleaner pattern: return `(rows, extra_headers)` from `load_tracker` and thread `extra_headers` through to `_write_tracker`. But this changes `load_tracker`'s return signature (currently returns 3-tuple `(wb, rows, job_ids)`), which breaks `append_rows` and `rebuild`.

**Simplest safe pattern (no signature change):** Store extra columns inline in the row list, PAST the `len(HEADERS)` boundary. `_write_tracker` currently breaks at `col > len(HEADERS)` — change this to continue writing any extra data:

```python
# In _write_tracker: replace the break with a pass-through
for col, val in enumerate(row, 1):
    if col > len(HEADERS):
        # User-added column: write raw value without scout formatting
        cell = ws.cell(row=r_idx, column=col, value=val)
        cell.fill = row_fill
        cell.border = THIN_BORDER
        cell.alignment = Alignment(wrap_text=True, vertical='top')
    else:
        # ... existing per-column formatting
```

And in `load_tracker`, read all columns (already done — `values_only=True` gets all values up to `ws.max_column`), and also discover user header names from row 1 for columns past `len(HEADERS)`.

**Also in `_write_tracker`, re-emit user headers** for the extra columns:
```python
# After standard HEADERS loop:
for i, extra_header in enumerate(user_extra_headers, len(HEADERS) + 1):
    cell = ws.cell(row=1, column=i, value=extra_header)
    # Apply same header formatting
```

**Test requirement:** A test that (a) creates a tracker with a user-added "My Notes" column, (b) calls `append_rows` to add a new row, (c) reopens the xlsx and asserts "My Notes" column and all its data are present. This test does NOT exist. Phase 5 must create it. [VERIFIED: `tests/` directory has no `test_tracker_utils.py`]

---

## ATS Regression-Suspect Logic (DDP-08)

The `runs.jsonl` `per_company_provider` field format (from `runs_log.py`):
```json
"per_company_provider": {
  "stripe|greenhouse": {"outcome": "OK_WITH_RESULTS", "listing_count": 5, "http_status": 200, "elapsed_seconds": 0.73},
  "airbnb|greenhouse": {"outcome": "OK_ZERO", "listing_count": 0, "http_status": 200, "elapsed_seconds": 0.5}
}
```

Regression-suspect rule (DDP-08): For any `(company, provider)` key that shows `OK_WITH_RESULTS` in ≥3 of the last 5 runs' `per_company_provider` entries, but shows `OK_ZERO` or `ERROR` in the CURRENT run: flag as "ATS regression suspect."

Implementation in SKILL.md Step 6 (Honest notes):
```bash
# Read last 6 lines of runs.jsonl (5 prior + 1 current written at Step 2.5)
python3 -c "
import json, sys
lines = [json.loads(l) for l in open('${RUNS_JSONL}').readlines()[-6:]]
# ... compare prior 5 vs current
"
```

This is a small inline Python one-liner or a new `runs_log.py` subcommand. The subcommand approach (`runs_log.py regression-suspects <runs_log_path> --lookback 5`) is cleaner and testable. [ASSUMED — no existing subcommand for regression analysis; adding one to runs_log.py follows the existing CLI dispatch pattern]

---

## Validation Architecture

`nyquist_validation: true` in `.planning/config.json`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (installed in `~/.job-scout-venv`) |
| Config file | none — runs via `~/.job-scout-venv/bin/python3 -m pytest tests/ -q` |
| Quick run command | `~/.job-scout-venv/bin/python3 -m pytest tests/test_dedup_phase5.py tests/test_tracker_phase5.py -q` |
| Full suite command | `~/.job-scout-venv/bin/python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DDP-01 | `dedupe.py cross-source` matches ATS vs LinkedIn listings by slug + title | unit | `pytest tests/test_dedup_phase5.py::test_cross_source_match -x` | ❌ Wave 0 |
| DDP-02 | Auto-merge at ≥95%, review-band at 70–94, keep-both at <70 | unit | `pytest tests/test_dedup_phase5.py::test_tiered_band -x` | ❌ Wave 0 |
| DDP-03 | Two-key gate: both loose AND tight must agree for auto-merge | unit | `pytest tests/test_dedup_phase5.py::test_two_key_gate -x` | ❌ Wave 0 |
| DDP-04 | `decisions` array present in dedup_result.json output | unit | `pytest tests/test_dedup_phase5.py::test_decisions_output -x` | ❌ Wave 0 |
| DDP-05 | ATS bump: ≤30d ATS listing gets +1 tier; >30d does not | unit (fixture-based) | `pytest tests/test_dedup_phase5.py::test_ats_tier_bump -x` | ❌ Wave 0 |
| CON-13 | `extract_linkedin_job_id` returns None for non-LinkedIn URLs | unit | `pytest tests/test_tracker_phase5.py::test_extract_linkedin_job_id -x` | ❌ Wave 0 |
| CON-13 | `extract_dedup_key` returns URL for non-LinkedIn rows | unit | `pytest tests/test_tracker_phase5.py::test_extract_dedup_key -x` | ❌ Wave 0 |
| CON-14 | `append_rows` result dict key is `flagged_stale`, value increments on stale rows | unit | `pytest tests/test_tracker_phase5.py::test_flagged_stale_count -x` | ❌ Wave 0 |
| CON-20 | User-added xlsx column survives `append_rows` round-trip | unit | `pytest tests/test_tracker_phase5.py::test_user_column_preservation -x` | ❌ Wave 0 |
| DDP-08 | Regression-suspect: company that had OK_WITH_RESULTS ≥3/5 but OK_ZERO today is flagged | unit | `pytest tests/test_dedup_phase5.py::test_regression_suspect -x` | ❌ Wave 0 |
| CON-15 | Pass-2 board with 0 results ≥3/5 runs is flagged "board appears broken" | integration (manual-only in SKILL; fixture for helper fn) | `pytest tests/test_dedup_phase5.py::test_board_broken_detection -x` | ❌ Wave 0 |
| DDP-06, DDP-07, CON-11, CON-12 | LinkedIn enrichment rules | manual-only (Chrome MCP, no automated path) | — | manual |

### Sampling Rate

- **Per task commit:** `~/.job-scout-venv/bin/python3 -m pytest tests/test_dedup_phase5.py tests/test_tracker_phase5.py -q`
- **Per wave merge:** `~/.job-scout-venv/bin/python3 -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_dedup_phase5.py` — covers DDP-01..05, DDP-08, CON-15
- [ ] `tests/test_tracker_phase5.py` — covers CON-13, CON-14, CON-20
- [ ] `tests/fixtures/linkedin_candidates_sample.json` — 3-listing Pass 2 fixture for cross-source dedup tests
- [ ] `tests/fixtures/ats_raw_sample/` — matching ATS listings for overlap scenarios
- [ ] Framework already installed: no new installs needed

---

## Common Pitfalls

### Pitfall 1: Enrich-then-tier ordering breaks if enrichment is called after tier assignment

**What goes wrong:** If Step 5 assigns tiers first (based on base score), then enriches only "A-tier" listings, a listing that would be A after the +1 bump but is B without it never gets enriched. The user misses the warm-path signal.

**How to avoid:** Enrich any listing where `base_score + 1_tier_bump_if_applicable >= A_threshold - N` (with N being a buffer, e.g. 5 points). In practice: enrich all ATS-sourced listings whose base score would be B-tier with a connection count > 0, plus all pre-bump A-tier ATS listings. The planner should specify the exact criterion explicitly. [ASSUMED — the exact "enrich first or after?" ordering needs a concrete rule]

### Pitfall 2: `load_tracker` returns extra-column data but `_write_tracker` drop guard is on `col > len(HEADERS)` with a `break`

**What goes wrong:** If a user's xlsx has a column 17 ("My Notes") and `_write_tracker` breaks at `col > 16`, the user's data is permanently lost on the next `append_rows` call. Existing `load_tracker` DOES read the extra values into memory (as extra list entries), so they're available — just not written back.

**How to avoid:** Replace `break` with a write-through path for extra columns. Also need to re-emit the user's extra HEADER names from row 1. Current `load_tracker` does NOT capture the header row — only data rows. Need to add header discovery. [VERIFIED: `load_tracker` starts `iter_rows(min_row=2)` — skips row 1 entirely]

### Pitfall 3: Two-key dedup with `_normalize_title` from `normalize.py` vs. a new normalization

**What goes wrong:** `normalize.py:_normalize_title` strips punctuation but preserves level markers. If `dedupe.py` imports this function, changes to it in Phase 5 affect both intra-source collapse (Phase 4) and cross-source dedup (Phase 5) simultaneously.

**How to avoid:** `dedupe.py` IMPORTS `_normalize_title` from `normalize.py` (do NOT copy-paste it). If Phase 5 needs different dedup normalization, add a SEPARATE function in `dedupe.py`. Coordinate: the function is currently "private" (leading underscore). Phase 5 plan must explicitly declare whether to make it public (`normalize_title`) or use a wrapper.

### Pitfall 4: `careers_url` column doesn't exist in schema; JSON-LD routing uses `career_page_url`

**What goes wrong:** Phase 4 VERIFICATION.md deferred item says "companies with `ats_provider == 'none'` AND `careers_url`" — but `careers_url` is NOT in `MASTER_TARGETS_COLUMNS`. The column in the schema is `career_page_url`. If the planner writes the SKILL.md step referencing `careers_url`, it silently finds nothing.

**How to avoid:** Use `career_page_url` (col 3 in `MASTER_TARGETS_COLUMNS`) for JSON-LD routing, not `careers_url`. [VERIFIED: `schema.py` `MASTER_TARGETS_COLUMNS` — col at index 2 is `career_page_url`]

### Pitfall 5: `runs.jsonl` regression-suspect check reads only the current run's line (written this same run)

**What goes wrong:** `runs.jsonl` is appended in Step 2.5. When Step 6 reads the last 6 lines for regression detection, line 6 (index -1) IS the current run. The "last 5 prior runs" are lines -6 through -2. If the SKILL naively reads "last 5 lines" for comparison, it includes the current run on both sides of the comparison.

**How to avoid:** The regression-suspect logic must explicitly read lines `[-6:-1]` (5 prior) and compare against line `[-1]` (current). A `runs_log.py regression-suspects` subcommand should encapsulate this offset, not leave it to the SKILL.

### Pitfall 6: `skipped_stale` rename in CON-14 vs. the returned dict key `flagged_stale`

**What goes wrong:** The REQUIREMENTS.md CON-14 says rename `skipped_stale` → `flagged_stale_count`. But the returned dict at line 263 already uses key `"flagged_stale"` (not `"flagged_stale_count"` and not `"skipped_stale"`). The SKILL.md at Step 7 reads this dict — if the key changes it breaks the SKILL's parsing.

**Resolution:** The returned dict key stays `"flagged_stale"` (already correct). Only the LOCAL VARIABLE `skipped_stale` (line 188) is renamed to `flagged_stale_count`. The dict key at line 263 is already right and must NOT be changed. [VERIFIED: `tracker_utils.py` line 263: `"flagged_stale": skipped_stale` — the return dict key is already `flagged_stale`, not `skipped_stale`]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Title fuzzy matching | Custom edit-distance | `rapidfuzz.token_set_ratio` | Already installed; handles abbreviation/word-order variation better than Levenshtein |
| xlsx column detection | Parse XML manually | `openpyxl.worksheet.ws.max_column` + `ws.cell(row=1, column=N).value` | openpyxl already loaded; header discovery via row 1 iteration |
| runs.jsonl line parsing | Custom JSONL reader | `[json.loads(l) for l in open(path).readlines()[-N:]]` | stdlib; runs.jsonl is append-only so no partial lines at tail |
| Pass-2 board tracking | Separate database | Add `pass2_boards` key to runs.jsonl stats.json | JSONL already established as the telemetry format |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pipeline_tier <= 2` priority sort | `linkedin_connection_count` threshold sort | Phase 5 (CON-09) | Removes dead column reference; sort already works this way in SKILL.md Step 2 |
| `pipeline_tier 1-3 +5 bonus` | `source=ats:* AND posted_date ≤ 30d → +1 tier` | Phase 5 (CON-10 + DDP-05) | ATS warm-path replaces dead pipeline concept |
| Career-page Chrome scraping in enrichment | LinkedIn-only Chrome MCP | Phase 5 (DDP-07) | Chrome scoped to LinkedIn; career-page Chrome deleted in Phase 6 |
| Generic `extract_job_id` (any 10+ digit run) | `extract_linkedin_job_id` (LinkedIn-anchored) + `extract_dedup_key` (URL-as-string) | Phase 5 (CON-13) | Fixes false stale-flagging on ATS career-page URLs |

---

## Open Questions

1. **Enrichment scope: pre-bump or post-bump A-tier?**
   - What we know: DDP-06 says "A-tier ATS candidates only." DDP-05 says +1 tier bump for ≤30d ATS listings.
   - What's unclear: does "A-tier" mean (a) A-tier from base rubric before applying the bump, or (b) A-tier after the bump is applied? A B-tier listing that becomes A after the bump needs enrichment to correctly render in the report. But enriching it before tier assignment means we enrich some listings that end up B-tier (no bump because >30d).
   - Recommendation: enrich any ATS listing whose base score + connection-leverage category score would reach B-tier or above. This is a conservative superset (may enrich a few B-tiers) but avoids missing A-tiers that only qualify post-bump. Confirm with user before planning.

2. **Pass-2 board-broken telemetry: runs.jsonl vs. separate file?**
   - What we know: CON-15 requires detecting ≥3/5 runs with 0 results. Current `runs.jsonl` has no Pass-2 board counts. Adding to runs.jsonl requires extending the `append_run()` schema or the stats.json CLI input.
   - What's unclear: is it acceptable to add a `pass2_boards` field to the runs.jsonl schema (slight schema expansion) or should this use a separate `<data_dir>/pass2_stats.jsonl`?
   - Recommendation: add `pass2_boards` to the existing runs.jsonl line (simpler, one file to read). The schema extension is additive and non-breaking for existing `jq` queries. Confirm with user.

3. **LinkedIn company slug for enrichment:**
   - What we know: enrichment navigates to `https://www.linkedin.com/company/<slug>/people/`. The slug is not the same as the ATS board slug.
   - What's unclear: should the SKILL derive the slug from `company_name` normalization (same approach as `detect-one`), or does `master_targets.csv` have/need a `linkedin_company_slug` column?
   - Recommendation: derive from `company_name` at run time (same normalization as Step 2b). If the navigation fails (404, login wall), log and continue — no new column needed. Confirm with user if a dedicated column is preferred.

4. **`dedup_decisions` in runs.jsonl: extend `append_run()` or use stats.json passthrough?**
   - What we know: DDP-04 says dedup decisions land in runs.jsonl. `append_run()` currently has a fixed schema. The CLI `runs_log.py append-run` reads a stats.json and passes known fields to `append_run()`.
   - What's unclear: cleanest extension path — add `dedup_decisions` kwarg to `append_run()` (requires code change to runs_log.py) vs. accept arbitrary extra keys in stats.json and merge them into the written line (requires looser schema).
   - Recommendation: add `dedup_decisions: Optional[List[dict]] = None` kwarg to `append_run()` and include it in the line dict if non-empty. This keeps the schema explicit. Confirm with user.

---

## Environment Availability

Step 2.6: SKIPPED (no new external dependencies — rapidfuzz, openpyxl, pytest already installed in `~/.job-scout-venv` from Phases 1-3).

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | `rapidfuzz.token_set_ratio` inputs are user-provided job titles — no SQL/command injection risk in a pure Python string comparison |
| V5 Input Validation (xlsx) | yes | `openpyxl` reads user-controlled xlsx; malformed file returns empty workbook, not code execution |
| V2 Authentication | no | No auth flows |
| V6 Cryptography | no | No secrets handled |

No new security surface is introduced by Phase 5. The xlsx passthrough (CON-20) reads user data from extra columns and re-emits it — this is the same trust model as the existing `_write_tracker` path. The `runs.jsonl` dedup_decisions field contains only slugs, URLs, and similarity scores — no PII from the candidate profile.

---

## Project Constraints (from CLAUDE.md)

**Critical conventions that affect Phase 5:**

| Constraint | Phase 5 Implication |
|------------|---------------------|
| All tracker writes go through `tracker_utils.py` | CON-20 fix ONLY touches `_write_tracker` and `load_tracker` — no other module writes xlsx |
| Worker threads do NOT call `tracker_utils.append_rows` | Dedup.py is invoked from SKILL Bash (main process) not from worker threads — safe |
| `scripts/ats/dedupe.py` sibling-bootstrap | Use 2-level bootstrap: `SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` |
| `try/except ImportError` with pipx/venv hint | `dedupe.py` imports `rapidfuzz` — needs the CON-04-compliant install hint pattern |
| Plain `print()` for logging, JSON as last stdout print | `dedupe.py` CLI subcommand `cross-source` must print dedup_result JSON as last stdout |
| `os.path.expanduser()` at boundary | `dedupe.py` CLI must expand `~` on all path args before use |
| Single source of truth: `schema.py` for columns, `file-contract.md` for paths | Any new files (dedup_result.json, pass2_stats.jsonl if chosen) must be added to `file-contract.md` |
| Model routing: delegate code generation to cf-code-assistant MCP | Executor agents must gather context first (this RESEARCH.md + actual source files) before calling `generateCode` |
| No `requirements.txt` — ImportError handlers print install hints | Applies to `dedupe.py`'s rapidfuzz import |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `append_run()` dedup_decisions extension: adding `Optional` kwarg is the cleanest path | Dedup Architecture | If runs_log.py is locked/frozen, alternative is stats.json passthrough; low risk |
| A2 | "A-tier candidate" for enrichment means pre-bump A-tier (base rubric) | Enrich-then-Tier | If post-bump interpretation is intended, some B→A bump candidates miss enrichment |
| A3 | `career_page_url` is the correct column to use for JSON-LD routing (not a `careers_url` column) | JSON-LD Routing | If a `careers_url` column exists in user data outside the canonical schema, URL routing would miss it |
| A4 | `templates/config.json` has no `dedup` section yet | Dedup Architecture | If it already has one with different key names, the plan must align to existing keys |
| A5 | LinkedIn company slug derivation from `company_name` at run time is sufficient (no dedicated column needed) | Enrich-then-Tier | If normalization produces wrong slug for common companies, enrichment navigates to wrong page silently |
| A6 | Pass-2 board-broken tracking goes in runs.jsonl (not a separate file) | CON-15 | If runs.jsonl schema should stay ATS-only, a separate file is needed; affects file-contract.md |

---

## Sources

### Primary (HIGH confidence)

- `scripts/tracker_utils.py` (HEAD) — verified all 4 `extract_job_id` callers, `_write_tracker` break guard, `skipped_stale` variable, returned dict key
- `scripts/ats/runs_log.py` (HEAD) — verified `append_run()` signature and line schema; no `dedup_decisions` kwarg currently
- `scripts/ats/normalize.py` (HEAD) — verified `_normalize_title` existence and implementation; `apply_filters` call order
- `scripts/ats/preview.py` (HEAD) — verified targets list building and pipe-split parsing; JSON-LD routing compatibility
- `scripts/ats/providers/jsonld.py` (HEAD) — verified `fetch(slug, client, sem)` accepts full URL as slug; `BOARD_URL_PATTERNS = []`
- `scripts/ats/dispatcher.py` (HEAD) — verified semaphore fallback for unknown providers (Semaphore(1))
- `scripts/schema.py` (HEAD) — verified `MASTER_TARGETS_COLUMNS` has `career_page_url` not `careers_url`; `TRACKER_COLUMNS` has 16 entries
- `skills/scout-run/SKILL.md` (HEAD) — verified Step 2.5 filter set; JSON-LD deferral note at line 168; Step 5 scoring flow
- `skills/job-scout/references/scoring-rubric.md` (HEAD) — verified dead `pipeline_tier 1-3 +5` row at line 111
- `skills/job-scout/references/search-config.md` (HEAD) — verified dead `pipeline_tier <= 2` reference at line 52
- `.planning/phases/04-.../04-VERIFICATION.md` — verified JSON-LD deferred item, gap closure record
- `.planning/config.json` — verified `nyquist_validation: true`
- `tests/` directory listing — verified no `test_tracker_phase5.py` or `test_dedup_phase5.py` exists yet

### Secondary (MEDIUM confidence)

- `.planning/research/SUMMARY.md` — rapidfuzz `token_set_ratio` dedup band thresholds (≥95/70–95/<70) — research-derived defaults, not production-measured
- `.planning/research/PITFALLS.md` lines 79-99 — dedup over/under-merge failure modes and mitigation patterns

### Tertiary (LOW confidence)

- None — all Phase 5 findings are codebase-verified or locked decisions from SUMMARY.md

---

## Metadata

**Confidence breakdown:**
- Dedup architecture: HIGH — all hook points verified against HEAD code
- JSON-LD routing: HIGH — verified `career_page_url` column, jsonld.py compatibility, preview.py CLI parsing
- CON-13/14/20 surgery: HIGH — all line numbers and code patterns verified
- CON-09/10 doc fixes: HIGH — verified exact line numbers and dead text
- Enrich-then-tier flow: MEDIUM-HIGH — flow verified; "A-tier candidate" scope is ASSUMED
- Regression-suspect logic: HIGH — `runs.jsonl` schema verified; offset arithmetic flagged in pitfalls
- Pass-2 board tracking: MEDIUM — mechanism clear; storage location (runs.jsonl vs. separate file) is open

**Research date:** 2026-04-28
**Valid until:** 2026-05-28 (stable codebase; no external API changes affect Phase 5)

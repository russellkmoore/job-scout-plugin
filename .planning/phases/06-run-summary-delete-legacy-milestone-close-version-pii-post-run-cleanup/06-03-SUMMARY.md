---
phase: "06"
plan: "03"
subsystem: "docs-version-pii"
tags: [version-bump, pii-callout, readme, chrome-setup, con-16, con-17, con-18, con-19, out-04, out-05, out-06]
dependency_graph:
  requires: []
  provides: [CON-16-partial, CON-17, CON-18, CON-19, OUT-04, OUT-05, OUT-06]
  affects: [skills/job-scout/SKILL.md, skills/scout-setup/SKILL.md, skills/scout-detect/SKILL.md, .claude-plugin/plugin.json, README.md]
tech_stack:
  added: []
  patterns: [blockquote-callout, schema-reference, ats-first-language]
key_files:
  created: []
  modified:
    - skills/job-scout/SKILL.md
    - skills/scout-setup/SKILL.md
    - skills/scout-detect/SKILL.md
    - .claude-plugin/plugin.json
    - README.md
decisions:
  - "chrome-setup.md required no edits — Phase 5 already scoped it to LinkedIn-only"
  - "scout-detect version was already 0.4.0 from Phase 3 — verified, not re-bumped (Pitfall 5)"
metrics:
  duration: "166s"
  completed: "2026-04-29"
  tasks_completed: 3
  files_modified: 5
---

# Phase 06 Plan 03: Doc/Version/PII Cleanup Bundle Summary

**One-liner:** Version lockstep bump (3 SKILL.md + plugin.json → 0.4.0), CON-17 inline column list deleted, CON-18/19 PII callout added, README updated with v0.4 capabilities.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Version lockstep bump + CON-16/CON-17 surgery | d3f970a | skills/job-scout/SKILL.md, skills/scout-setup/SKILL.md, skills/scout-detect/SKILL.md, .claude-plugin/plugin.json |
| 2 | PII callout + .gitignore template (CON-18, CON-19) | 5b8a12a | skills/scout-setup/SKILL.md |
| 3 | README v0.4 capabilities + chrome-setup verify | 71c12be | README.md (chrome-setup.md verified clean, no edit needed) |

## Version State After This Plan

| File | Before | After | Owner |
|------|--------|-------|-------|
| `.claude-plugin/plugin.json` | 0.3.3 | **0.4.0** | This plan |
| `skills/job-scout/SKILL.md` | 0.3.0 | **0.4.0** | This plan |
| `skills/scout-setup/SKILL.md` | 0.3.1 | **0.4.0** | This plan |
| `skills/scout-detect/SKILL.md` | 0.4.0 (already) | **0.4.0** (verified) | Phase 3 |
| `skills/scout-run/SKILL.md` | 0.3.3 | 0.3.3 (awaiting Plan 06-04) | Plan 06-04 |

**Version lockstep gate after this plan:** `grep -h "^version:" skills/*/SKILL.md | grep -c "0.4.0"` = 3. Will become 4 after Plan 06-04 lands.

## CON-17 Surgery Confirmation

- **Target:** `skills/job-scout/SKILL.md` line 38 (inline column enumeration)
- **Before:** `Includes \`company_name\`, \`industry\`, \`career_page_url\`, **\`ats_provider\`**, ...`
- **After:** `See \`scripts/schema.py:MASTER_TARGETS_COLUMNS\` for the canonical column list.`
- **Verification:** `grep -c "Includes \`company_name\`" skills/job-scout/SKILL.md` = 0 ✓
- **Verification:** `grep -c "scripts/schema.py:MASTER_TARGETS_COLUMNS" skills/job-scout/SKILL.md` = 1 ✓
- **Note:** `career_page_url` references in body text outside line 38 were preserved — CON-17 surgery was line-38-only as specified.

## CON-18 + CON-19 Callout Location

- **Insertion point:** After Step 1 question 5 (data directory question, `mkdir -p` line), before the `---` separator.
- **Format:** Markdown blockquote (`>` prefix on every line) including fenced code block inside blockquote.
- **Content covers:**
  - `connections_summary.csv` + `master_targets.csv:connection_names` — third-party connection data
  - `candidate_profile.json` — salary targets + skill assessments
  - `config.json:candidate.resume_path` — filesystem path
  - Do-not-place locations: iCloud Drive, Dropbox, OneDrive, Google Drive
  - Recommended location: `~/Documents/JobSearch/` (local-only macOS default)
  - Redact `candidate.resume_path` warning before sharing config
  - `.gitignore` template with 6 entries + `# Job Scout data directory` comment header

## chrome-setup.md Verification Result (OUT-04 / OUT-05)

`grep -c "marketing\|career.*page.*scrape" skills/job-scout/references/chrome-setup.md` = **0**

No edits were required. Phase 5 (CON-11/CON-12 work) had already scoped this file to LinkedIn-only. The borderline line 72 (`Career pages and ATS boards (Greenhouse, Lever, Workday, Ashby) generally return full JDs on first navigation`) was reviewed and confirmed to be explanatory prose (explaining why the LinkedIn lazy-load dance is LinkedIn-specific), not scraping instructions. The regex `career.*page.*scrape` does not match it.

## README v0.4 Section Anchor Location

- **`## What's new in v0.4`** inserted between `## What it does` and `## Requirements` sections.
- 7 capability bullets: ATS-first sourcing, JSON-LD fallback, /scout-detect skill, cross-source dedup, enrich-then-tier, structured observability, milestone bar.
- D-2 wall-clock scope documented explicitly in milestone bar bullet: `wall_clock_avg_seconds (target ≤ 300s, ATS-fetch only — not total /scout-run wall-clock)`.
- Pass 1 description in "What it does" rewritten to ATS-first language; Chrome marketing-page framing removed.
- Install hint updated from `pip install pandas openpyxl` to `pipx install` / `python3 -m venv` (CON-04 alignment).
- Versioning section: 0.4.0 entry added as first bullet before 0.3.0.

## Deviations from Plan

None — plan executed exactly as written.

- chrome-setup.md required no edits (Phase 5 already clean) — this was anticipated in the plan as a possible outcome.
- cf-code-assistant MCP delegation was assessed as not applicable (all changes were surgical edits to existing text with exact before/after strings provided in the plan's `<interfaces>` block; no generative workload).

## Requirements Addressed

| Req | Description | Status |
|-----|-------------|--------|
| CON-16 | Version lockstep: 3-of-4 SKILL.md + plugin.json at 0.4.0 | Delivered (Plan 06-04 lifts to 4-of-4) |
| CON-17 | Inline column list deleted from job-scout/SKILL.md line 38 | Delivered |
| CON-18 | PII callout naming sensitive files + cloud-sync warning | Delivered |
| CON-19 | .gitignore template + resume_path redaction warning | Delivered |
| OUT-04 | chrome-setup.md verified free of marketing-page scraping prose | Verified |
| OUT-05 | chrome-setup.md trimmed if needed | No edits needed (already clean) |
| OUT-06 | README v0.4 capabilities section + plugin.json description update | Delivered |

## Known Stubs

None — all changes are documentation/configuration. No data-flow stubs introduced.

## Threat Flags

None — documentation-only changes. T-06-06 (PII callout) mitigated by the callout itself (CON-18/19). No new network endpoints, auth paths, or write paths introduced.

## Self-Check: PASSED

Files verified present:
- `skills/job-scout/SKILL.md` — version 0.4.0, no inline column list ✓
- `skills/scout-setup/SKILL.md` — version 0.4.0, PII callout present ✓
- `skills/scout-detect/SKILL.md` — version 0.4.0 (pre-existing), [ATS-PREVIEW] removed ✓
- `.claude-plugin/plugin.json` — version 0.4.0, 5 providers named ✓
- `README.md` — What's new in v0.4 section present ✓

Commits verified:
- d3f970a — Task 1 (version bump + CON-16/17) ✓
- 5b8a12a — Task 2 (CON-18/19 PII callout) ✓
- 71c12be — Task 3 (README + chrome-setup verify) ✓
